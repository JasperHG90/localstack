#!/usr/bin/env bash
# Does `terraform providers schema -json` pass offline on a healthy root and
# fail when providers are missing or truncated? Exit 0 only if so.
# Runs every probe in a fresh network namespace (unshare -rn: no network at
# all, so neither the registry nor the Consul backend is reachable), with a
# dead proxy and no NOMAD_ADDR/VAULT_ADDR/CONSUL_HTTP_ADDR.
set -u
SRC=/home/vscode/workspace/deployments/infrastructure
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
cp -a "$SRC" "$W/healthy"

probe() { # name dir expect(pass|fail)
  local name=$1 dir=$2 expect=$3 start rc dur conns
  start=$EPOCHREALTIME
  env -u NOMAD_ADDR -u VAULT_ADDR -u CONSUL_HTTP_ADDR \
    HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
    unshare -rn strace -f -qq -e trace=connect -o "$W/$name.strace" \
    terraform -chdir="$dir" providers schema -json >/dev/null 2>"$W/$name.err"
  rc=$?
  dur=$(awk "BEGIN{printf \"%.2f\", $EPOCHREALTIME - $start}")
  conns=$(grep -c 'AF_INET' "$W/$name.strace" || true)
  echo "== $name: exit=$rc time=${dur}s inet_connects=$conns expect=$expect"
  grep -E 'AF_INET' "$W/$name.strace" | head -5
  sed 's/^/   stderr: /' "$W/$name.err" | head -12
  if [ "$expect" = pass ] && [ $rc -ne 0 ]; then FAIL=1; fi
  if [ "$expect" = fail ] && [ $rc -eq 0 ]; then FAIL=1; fi
}
FAIL=0
P=.terraform/providers/registry.terraform.io/hashicorp

probe healthy "$W/healthy" pass

cp -al "$W/healthy" "$W/one_missing"; rm -rf "$W/one_missing/$P/vault"
probe one_missing "$W/one_missing" fail

cp -al "$W/healthy" "$W/empty_providers"; rm -rf "$W/empty_providers/.terraform/providers"/*
probe empty_providers "$W/empty_providers" fail

# A download cut off mid-stream: binary present but truncated.
cp -al "$W/healthy" "$W/truncated"
bin=$(ls "$W/truncated/$P"/null/*/*/terraform-provider-null*)
head -c 1000000 "$bin" > "$bin.part"; rm "$bin"; mv "$bin.part" "$bin"; chmod +x "$bin"
probe truncated "$W/truncated" fail

echo "RESULT: FAIL=$FAIL"
exit $FAIL
