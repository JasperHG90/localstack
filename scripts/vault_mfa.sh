# Mint and revoke the per-person TOTP secret for Vault login MFA.
#
# The TOTP method and its login enforcement belong to Terraform
# (deployments/infrastructure/identity.tf). This script owns only the secret,
# which Terraform must never hold: that secret IS the second factor, so putting
# it in state would file both factors in the same place.
#
# The method id is looked up, never passed in. Vault generates it on create, so
# any literal goes stale the first time the method is replaced.
#
# THE TRAP: `admin-generate` against an entity that already has a secret exits
# 0 and returns `data: null`, with the real message in `warnings`. Piping that
# to `base64 -d` writes a 0-byte PNG and reports success. Measured on Vault
# 2.0.3, 2026-09-11. `generate` checks both the null and the decoded PNG magic,
# because a non-null response can still carry an empty barcode.
#
# Re-enrolling is therefore destroy-then-generate, which is `reset`. It
# invalidates the old authenticator; Vault stores one secret per entity per
# method, so there is no way to have both live at once.

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: vault_mfa.sh status
       vault_mfa.sh enroll <username>
       vault_mfa.sh reset  <username>
EOF
  exit 64
}

require_vault() {
  [ -n "${VAULT_ADDR:-}" ] || { echo "VAULT_ADDR is unset; run: eval \"\$(localstack env)\"" >&2; exit 1; }
}

# `vault list -format=json` prints `{}` on stdout and exits 2 when the path holds
# nothing. A `|| echo '[]'` fallback APPENDS to that rather than replacing it,
# which yields `{}\n[]`, makes `jq length` print "0\n0", and matches neither 0
# nor 1 in a case statement. Every listing goes through here so that is settled
# once. Measured on Vault 2.0.3, 2026-09-11.
list_keys() {
  local out
  out=$(vault list -format=json "$1" 2>/dev/null) || return 0
  echo "$out" | jq -r 'if type == "array" then .[] else empty end' 2>/dev/null || true
}

# Who a userpass enforcement would cover: entities holding an alias on that
# mount. That is the real criterion. The `kind = "human"` metadata is not, since
# an entity created outside Terraform does not carry it.
userpass_entities() {
  local accessor
  accessor=$(vault auth list -format=json | jq -r '.["userpass/"].accessor')
  list_keys identity/entity/id \
    | while read -r id; do
        vault read -format=json "identity/entity/id/$id" \
          | jq -r --arg a "$accessor" \
            'select(any(.data.aliases[]?; .mount_accessor == $a)) | "  \(.data.name)"'
      done
}

# Exactly one method, or refuse. Two methods means an enforcement could name
# either and this script would silently pick the wrong one.
method_id() {
  local ids count
  ids=$(list_keys identity/mfa/method)
  if [ -z "$ids" ]; then count=0; else count=$(printf '%s\n' "$ids" | wc -l); fi
  case "$count" in
    0) echo "no TOTP method exists. Apply deployments/infrastructure first." >&2; exit 1 ;;
    1) echo "$ids" ;;
    *) echo "more than one MFA method exists; this script will not guess:" >&2
       # Print the ids from the listing directly. An earlier version re-read
       # each one to add its issuer, which printed NOTHING when a method was
       # deleted between the list and the read, leaving an empty complaint.
       printf '  %s\n' $ids >&2
       echo "Inspect them with 'just mfa_status', then delete the strays:" >&2
       echo "  vault delete identity/mfa/method/totp/<id>" >&2
       exit 1 ;;
  esac
}

# Names are the userpass usernames (`operator`, `veerle`), not display names.
# Pass the name through verbatim: the Vault CLI encodes the path itself, and
# pre-encoding a space as %20 makes the lookup miss.
entity_id() {
  vault read -field=id "identity/entity/name/$1" 2>/dev/null || {
    echo "no Vault entity named '$1'. Entities that log in through userpass:" >&2
    userpass_entities >&2
    exit 1
  }
}

# Writes the QR to tmp/, which the repo gitignores. The PNG carries the seed in
# full, so it is a secret until it is scanned and deleted.
generate() {
  local mid=$1 eid=$2 username=$3 out response scratch
  out="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)/tmp/vault-totp-${username// /_}.png"
  mkdir -p "$(dirname "$out")"

  response=$(vault write -format=json identity/mfa/method/totp/admin-generate \
    method_id="$mid" entity_id="$eid")

  if [ "$(echo "$response" | jq -r '.data')" = "null" ]; then
    echo "Vault refused to generate a secret:" >&2
    echo "$response" | jq -r '.warnings[]?' >&2
    echo "If they lost their authenticator, use: just mfa_reset '$username'" >&2
    exit 1
  fi

  # Decode beside the target, never over it: a bad response must not destroy the
  # QR already sitting there. `base64 -d` exits 0 on an empty barcode and on the
  # literal "null", so the PNG magic is what actually gets checked. An empty
  # barcode is reachable: `qr_size = 0` on the method is a valid Terraform
  # attribute and makes Vault return one.
  scratch=$(mktemp "${out}.XXXXXX")
  echo "$response" | jq -r '.data.barcode' | base64 -d > "$scratch" 2>/dev/null || true
  if [ "$(head -c 8 "$scratch" | od -An -tx1 | tr -d ' \n')" != "89504e470d0a1a0a" ]; then
    echo "Vault returned no usable PNG ($(wc -c < "$scratch") bytes decoded)." >&2
    echo "Nothing was written; any existing QR at $out is untouched." >&2
    rm -f "$scratch"
    exit 1
  fi
  mv "$scratch" "$out"
  echo ">> wrote $out"
  echo ">> scan it, confirm a code works, then delete it: rm '$out'"
  echo ">> the app will label this '<issuer> ($eid)'; rename it to '$username' by hand."
}

require_vault

case "${1:-}" in
  status)
    [ $# -eq 1 ] || usage
    echo "=== TOTP methods ==="
    methods=$(list_keys identity/mfa/method)
    if [ -z "$methods" ]; then
      echo "(none)"
    else
      printf '%s\n' "$methods" | while read -r id; do
        vault read -format=json "identity/mfa/method/totp/$id" \
          | jq -r '"\(.data.id)  issuer=\(.data.issuer)  \(.data.algorithm)/\(.data.digits) digits/\(.data.period)s"'
      done
    fi

    echo
    echo "=== login enforcements ==="
    enforcements=$(list_keys identity/mfa/login-enforcement)
    if [ -z "$enforcements" ]; then
      echo "(none)"
    else
      printf '%s\n' "$enforcements" | while read -r name; do
        vault read -format=json "identity/mfa/login-enforcement/$name" \
          | jq -r --argjson mounts "$(vault auth list -format=json | jq 'to_entries|map({(.value.accessor):.key})|add')" \
            '"\(.data.name)  mounts=\([.data.auth_method_accessors[]? | $mounts[.] // .] | join(","))  entities=\(.data.identity_entity_ids|length)  groups=\(.data.identity_group_ids|length)"'
      done
    fi

    echo
    echo "=== entities logging in through userpass ==="
    userpass_entities

    echo
    echo "Vault exposes no endpoint listing which entities hold a TOTP secret,"
    echo "so who is enrolled cannot be read back. The names above are who a"
    echo "userpass enforcement covers, which is who needs enrolling."
    ;;

  enroll)
    [ $# -eq 2 ] || usage
    mid=$(method_id); eid=$(entity_id "$2")
    generate "$mid" "$eid" "$2"
    ;;

  reset)
    [ $# -eq 2 ] || usage
    mid=$(method_id); eid=$(entity_id "$2")
    # Idempotent: succeeds whether or not a secret was there.
    vault write identity/mfa/method/totp/admin-destroy method_id="$mid" entity_id="$eid" >/dev/null
    echo ">> destroyed any existing secret for '$2'"
    generate "$mid" "$eid" "$2"
    ;;

  *) usage ;;
esac
