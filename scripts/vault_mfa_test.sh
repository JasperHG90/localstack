# Tests for vault_mfa.sh, driven by a fake `vault` on PATH.
#
# Run: just mfa_test
#
# The fake matters more than it looks. `vault list -format=json` on an EMPTY
# path prints `{}` on stdout and exits 2, and reproducing that exactly is the
# point: a fake returning `[]` or nothing would pass while the real script told
# the operator "more than one MFA method exists" against an empty Vault. That
# bug reached the operator twice before this file existed.

set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="$HERE/vault_mfa.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PASS=0
FAIL=0

mkdir -p "$WORK/bin"
cat > "$WORK/bin/vault" <<'FAKE'
#!/usr/bin/env bash
case "$1:${3:-}" in
  list:identity/mfa/method)
    case "$SCENARIO" in
      # Real Vault on an empty path: `{}` on stdout, exit 2.
      no-methods)  echo '{}'; exit 2 ;;
      two-methods) echo '["method-1","method-2"]'; exit 0 ;;
      *)           echo '["method-1"]'; exit 0 ;;
    esac ;;
  list:identity/mfa/login-enforcement) echo '{}'; exit 2 ;;
  list:identity/entity/id)             echo '["e1"]'; exit 0 ;;
esac

case "$*" in
  *"identity/entity/name/operator"*) echo "entity-operator"; exit 0 ;;
  *"identity/entity/name/"*)         exit 2 ;;
  *"identity/entity/id/e1"*)
    echo '{"data":{"name":"operator","aliases":[{"mount_accessor":"auth_userpass_x"}]}}'; exit 0 ;;
esac

[ "$1" = "auth" ] && { echo '{"userpass/":{"accessor":"auth_userpass_x"}}'; exit 0; }

if [ "$1" = "write" ]; then
  case "$*" in *admin-destroy*) echo "destroyed"; exit 0 ;; esac
  case "$SCENARIO" in
    already-enrolled) echo '{"data":null,"warnings":["Entity already has a secret"]}'; exit 0 ;;
    empty-barcode)    echo '{"data":{"barcode":"","url":"otpauth://x"}}'; exit 0 ;;
    *) echo "{\"data\":{\"barcode\":\"$(printf '\x89PNG\r\n\x1a\nbody' | base64 -w0)\",\"url\":\"otpauth://x\"}}"; exit 0 ;;
  esac
fi
exit 1
FAKE
chmod +x "$WORK/bin/vault"

run() {
  local scenario=$1; shift
  SCENARIO="$scenario" PATH="$WORK/bin:$PATH" VAULT_ADDR=http://fake \
    bash "$SCRIPT" "$@" 2>&1
}

want() {
  local name=$1 needle=$2 actual=$3
  if echo "$actual" | grep -qF -- "$needle"; then
    echo "  pass  $name"; PASS=$((PASS + 1))
  else
    echo "  FAIL  $name"
    echo "        wanted: $needle"
    echo "        got:    $(echo "$actual" | head -2 | tr '\n' '|')"
    FAIL=$((FAIL + 1))
  fi
}

deny() {
  local name=$1 needle=$2 actual=$3
  if echo "$actual" | grep -qF -- "$needle"; then
    echo "  FAIL  $name"
    echo "        must not contain: $needle"
    FAIL=$((FAIL + 1))
  else
    echo "  pass  $name"; PASS=$((PASS + 1))
  fi
}

echo "vault_mfa.sh"

out=$(run no-methods enroll operator)
want "empty Vault reports no method"            "no TOTP method exists" "$out"
deny "empty Vault never claims more than one"   "more than one"         "$out"

out=$(run two-methods enroll operator)
want "two methods refuses"          "more than one MFA method exists" "$out"
want "two methods lists id 1"       "method-1"                        "$out"
want "two methods lists id 2"       "method-2"                        "$out"

out=$(run one-method enroll nobody)
want "unknown entity is named"      "no Vault entity named 'nobody'"  "$out"
want "unknown entity lists members" "operator"                        "$out"

out=$(run already-enrolled enroll operator)
want "already enrolled refuses"     "Entity already has a secret"     "$out"
want "already enrolled -> reset"    "just mfa_reset"                  "$out"

out=$(run empty-barcode enroll operator)
want "empty barcode refuses"        "no usable PNG"                   "$out"
want "empty barcode keeps old QR"   "untouched"                       "$out"

out=$(run good enroll operator)
want "good response writes a QR"    "wrote"                           "$out"

out=$(run good reset operator)
want "reset destroys first"         "destroyed any existing secret"   "$out"
want "reset then writes a QR"       "wrote"                           "$out"

out=$(run no-methods status)
want "status survives an empty Vault" "(none)"                        "$out"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
