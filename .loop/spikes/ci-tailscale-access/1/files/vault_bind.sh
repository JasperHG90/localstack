#!/usr/bin/env bash
# Spike ci-tailscale-access risk 3: does a Vault JWT role bound on repository, ref,
# environment and workflow_ref accept only the probe.yaml/main/lab token?
# Args: directory holding one file per case, named <case>.jwt, with expected
# outcome in the name prefix: accept_*.jwt or refuse_*.jwt. Exit 0 only if every
# case matches. Starts and removes a local dev Vault (hashicorp/vault:1.21.1).
set -uo pipefail
dir=$1
name=spike-ts3-vault
docker rm -f $name >/dev/null 2>&1
docker run -d --name $name -p 18200:8200 -e VAULT_DEV_ROOT_TOKEN_ID=root --cap-add IPC_LOCK hashicorp/vault:1.21.1 >/dev/null
trap 'docker rm -f $name >/dev/null 2>&1' EXIT
v() { docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=root $name vault "$@"; }
for i in $(seq 30); do v status >/dev/null 2>&1 && break; sleep 1; done
echo "vault $(v version)"
v auth enable -path=jwt-github jwt
v write auth/jwt-github/config oidc_discovery_url=https://token.actions.githubusercontent.com bound_issuer=https://token.actions.githubusercontent.com
v write auth/jwt-github/role/probe - <<'JSON'
{"role_type":"jwt","user_claim":"repository","bound_audiences":["spike-only-not-trusted"],
 "bound_claims_type":"string",
 "bound_claims":{"repository":"JasperHG90/lab-auth-probe","ref":"refs/heads/main","environment":"lab",
   "workflow_ref":"JasperHG90/lab-auth-probe/.github/workflows/probe.yaml@refs/heads/main"},
 "token_ttl":"60s"}
JSON
v read -format=json auth/jwt-github/role/probe | jq -c '.data|{bound_audiences,bound_claims,bound_claims_type,user_claim}'
fail=0
for f in "$dir"/*.jwt; do
  case=$(basename "$f" .jwt)
  out=$(v write -format=json auth/jwt-github/login role=probe jwt="$(cat "$f")" 2>&1)
  if [ $? -eq 0 ]; then got=accept; detail=$(jq -c '.auth.metadata' <<<"$out"); else got=refuse; detail=$(tr '\n' ' ' <<<"$out" | grep -o '\* .*' | head -c 300); fi
  want=${case%%_*}
  [ "$got" = "$want" ] && r=OK || { r=MISMATCH; fail=1; }
  echo "$r case=$case want=$want got=$got :: $detail"
done
exit $fail
