#!/usr/bin/env bash
# Read-only: are any S2 PoC leftovers still live? Exits 0 only when none are.
set -uo pipefail
eval "$(localstack env 2>/dev/null)"
found=0

echo "== vault database mounts"
mounts=$(vault secrets list -format=json)
echo "$mounts" | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(k, v["type"]) for k,v in d.items() if v["type"]=="database"]'
if echo "$mounts" | python3 -c 'import json,sys; sys.exit(0 if "database/" in json.load(sys.stdin) else 1)'; then
  echo "LEFTOVER: database/ mount"; found=1
  vault list database/config 2>&1; vault list database/roles 2>&1
fi

echo "== kv secret/default/postgres/vault-dbengine-admin"
if vault kv metadata get -mount=secret default/postgres/vault-dbengine-admin >/dev/null 2>&1; then
  echo "LEFTOVER: kv entry exists"; found=1
  vault kv metadata get -format=json -mount=secret default/postgres/vault-dbengine-admin \
    | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; print("versions", {k:(v["deletion_time"] or "live", v["destroyed"]) for k,v in d["versions"].items()})'
else
  echo "absent"
fi

echo "== postgres role vault-dbengine-admin and v-* minted roles"
export PGH=$(curl -s -H "X-Consul-Token: ${CONSUL_HTTP_TOKEN}" "${CONSUL_HTTP_ADDR}/v1/catalog/service/postgres-db" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["Address"])')
export PGU=$(vault kv get -mount=secret -field=username default/postgres/localstack)
export PGP=$(vault kv get -mount=secret -field=password default/postgres/localstack)
roles=$(uv run --quiet --no-project --with 'psycopg[binary]' python -I -c '
import os, psycopg
with psycopg.connect(host=os.environ["PGH"], user=os.environ["PGU"], password=os.environ["PGP"], dbname="postgres", connect_timeout=10) as c:
    for (r,) in c.execute("select rolname from pg_roles where rolname = %s or rolname like %s order by 1", ("vault-dbengine-admin", "v-%")):
        print(r)
')
echo "${roles:-none}"
[ -n "$roles" ] && { echo "LEFTOVER: postgres roles"; found=1; }

echo "== applications state addresses (read-only state list)"
addrs=$(CONSUL_HTTP_TOKEN=${CONSUL_HTTP_TOKEN} terraform -chdir=/home/vscode/workspace/deployments/applications state list 2>&1)
rc=$?
echo "state list rc=$rc, $(echo "$addrs" | wc -l) addresses"
[ $rc -ne 0 ] && { echo "$addrs" | tail -5; found=2; }
hits=$(echo "$addrs" | grep -E 's2_poc|vault_mount\.database|postgres_poc|vault_database_secret_backend|dbengine' || true)
echo "${hits:-no s2/database-secrets addresses}"
[ -n "$hits" ] && { echo "LEFTOVER: state addresses"; found=1; }

echo "found=$found"
exit $found
