#!/usr/bin/env bash
# On a copy of deployments/infrastructure:
#  (c) healthy root: offline validate passes, no network call.
#  (a) one / all providers removed: offline validate fails with
#      "Missing required provider" or "Required plugins are not installed",
#      no network call.
#  (b) init -backend=false (network allowed) heals it: offline validate then
#      passes, and .terraform/terraform.tfstate (the Consul backend record)
#      is unchanged; init makes no connection to the Consul host.
# Exit 0 only if all hold.
set -u
SRC=/home/vscode/workspace/deployments/infrastructure
SCRATCH=/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2
W=$(mktemp -d "$SCRATCH/run.XXXX")
trap 'rm -rf "$W"' EXIT
# services.tf reads ${path.root}/../../.ssh/id_rsa, so copies sit two levels
# below a dir holding a dummy key.
mkdir -p "$W/.ssh" "$W/d"; echo dummy > "$W/.ssh/id_rsa"
cp -a "$SRC" "$W/d/healthy"
export NOMAD_ADDR=http://127.0.0.1:4646
P=.terraform/providers/registry.terraform.io/hashicorp
FAIL=0
MSG='Missing required provider|Required plugins are not installed'

# Count connects to anything other than loopback / unix sockets.
ext_conns() { grep -E 'AF_INET6?' "$1" | grep -v -E '127\.0\.0\.1|::1' | grep -c . || true; }

validate_offline() { # name dir expect(pass|fail)
  local name=$1 dir=$2 expect=$3 rc conns msg
  unshare -rn strace -f -qq -e trace=connect -o "$W/$name.vstrace" \
    terraform -chdir="$dir" validate -no-color >"$W/$name.vout" 2>&1
  rc=$?
  conns=$(ext_conns "$W/$name.vstrace")
  if grep -qE "$MSG" "$W/$name.vout"; then msg=yes; else msg=no; fi
  echo "   provider lines: $(grep -E 'no package for|missing or corrupted|Missing required provider|Required plugins' "$W/$name.vout" | head -2 | tr -s ' ')"
  echo "== validate $name: exit=$rc external_connects=$conns provider_msg=$msg expect=$expect"
  grep -E 'AF_INET' "$W/$name.vstrace" | head -3
  sed 's/^/   | /' "$W/$name.vout" | head -8
  [ "$conns" -eq 0 ] || FAIL=1
  if [ "$expect" = pass ]; then [ $rc -eq 0 ] || FAIL=1; fi
  if [ "$expect" = fail ]; then { [ $rc -ne 0 ] && [ $msg = yes ]; } || FAIL=1; fi
}

heal() { # name dir
  local name=$1 dir=$2 rc before after consul
  before=$(sha256sum "$dir/.terraform/terraform.tfstate" | cut -d' ' -f1)
  strace -f -qq -e trace=connect -o "$W/$name.istrace" \
    terraform -chdir="$dir" init -backend=false -input=false -no-color >"$W/$name.iout" 2>&1
  rc=$?
  if [ -f "$dir/.terraform/terraform.tfstate" ]; then
    after=$(sha256sum "$dir/.terraform/terraform.tfstate" | cut -d' ' -f1)
  else after=REMOVED; fi
  consul=$(grep -c '192\.168\.2\.30' "$W/$name.istrace" || true)
  echo "== init $name: exit=$rc consul_connects=$consul tfstate_before=${before:0:12} after=${after:0:12}"
  grep -E 'Installing|Installed|Reusing|Error' "$W/$name.iout" | sed 's/^/   | /' | head -8
  [ $rc -eq 0 ] || FAIL=1
  [ "$before" = "$after" ] || { echo "   tfstate CHANGED"; FAIL=1; }
  [ "$consul" -eq 0 ] || FAIL=1
  grep -q '"type": "consul"' "$dir/.terraform/terraform.tfstate" 2>/dev/null \
    && echo "   backend record still consul" || { echo "   backend record lost"; FAIL=1; }
}

validate_offline healthy "$W/d/healthy" pass

cp -a "$W/d/healthy" "$W/d/one_missing"; rm -rf "$W/d/one_missing/$P/vault"
validate_offline one_missing "$W/d/one_missing" fail

cp -a "$W/d/healthy" "$W/d/all_missing"; rm -rf "$W/d/all_missing/.terraform/providers"
validate_offline all_missing "$W/d/all_missing" fail

heal one_missing "$W/d/one_missing"
validate_offline one_missing_healed "$W/d/one_missing" pass

heal all_missing "$W/d/all_missing"
validate_offline all_missing_healed "$W/d/all_missing" pass

# CI-shaped root: no backend record at all (init -backend=false from scratch).
cp -a "$W/d/healthy" "$W/d/ci_missing"; rm -rf "$W/d/ci_missing/.terraform/providers" "$W/d/ci_missing/.terraform/terraform.tfstate"
validate_offline ci_missing "$W/d/ci_missing" fail
strace -f -qq -e trace=connect -o "$W/ci.istrace" terraform -chdir="$W/d/ci_missing" init -backend=false -input=false -no-color >"$W/ci.iout" 2>&1
echo "== init ci_missing (no backend record): exit=$? consul_connects=$(grep -c '192\.168\.2\.30' "$W/ci.istrace")"
grep -E 'Error' "$W/ci.iout" | head -3
validate_offline ci_missing_healed "$W/d/ci_missing" pass

cmp -s "$SRC/.terraform.lock.hcl" "$W/d/all_missing/.terraform.lock.hcl" \
  && echo "== lock file unchanged by init" || echo "== lock file changed by init (informational)"

echo "RESULT: FAIL=$FAIL"
exit $FAIL
