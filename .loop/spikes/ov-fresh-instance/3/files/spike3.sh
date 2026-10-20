#!/usr/bin/env bash
# Spike ov-fresh-instance risk 1: on an empty bucket and empty schema, does
# OpenViking v0.4.17.1-9 under auth_mode oidc serve ls, write and search for a
# token with ov_account=lab, ov_user=jasper, and which accounts/users exist in
# the bucket afterwards? Exits 0 only if every call passes and the bucket holds
# no _system/ key and nothing outside lab/ but the preset default tree.
# If the OIDC calls fail, it tries the fallback (api_key boot + root key +
# POST /admin/accounts, then OIDC again) and reports it, but still exits 1.
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot
export UV_CACHE_DIR=$D/uvcache
REPO=$(git rev-parse --show-toplevel)
OV_IMG=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
P=spike-ovboot
NET=$P-net
W=$(mktemp -d -p "$D")
cleanup() { docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1
docker network create $NET >/dev/null

cat >"$W/s3.json" <<'J'
{"identities": [{"name": "admin",
  "credentials": [{"accessKey": "SPIKEADMINKEY0000001", "secretKey": "spikeAdminSecret0000000000000000000000001"}],
  "actions": ["Admin", "Read", "Write", "List", "Tagging"]}]}
J
docker create --name $P-swfs --network $NET --network-alias swfs -p 127.0.0.1::8333 chrislusf/seaweedfs:4.48 \
  server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=64 \
  -s3 -s3.port=8333 -s3.config=/s3.json >/dev/null
docker cp "$W/s3.json" $P-swfs:/s3.json
docker start $P-swfs >/dev/null
docker run -d --name $P-pg --network $NET --network-alias pg -e POSTGRES_USER=ov -e POSTGRES_PASSWORD=ov \
  -e POSTGRES_DB=openviking pgvector/pgvector:pg17 >/dev/null
docker run -d --name $P-fake --network $NET --network-alias fake -v "$D/fake.py:/fake.py:ro" \
  --entrypoint /app/.venv/bin/python $OV_IMG -I /fake.py http://fake:8000 >/dev/null

for _ in $(seq 60); do docker exec $P-pg pg_isready -U ov -d openviking >/dev/null 2>&1 && break; sleep 1; done
docker exec $P-pg psql -qU ov -d openviking -c 'CREATE EXTENSION IF NOT EXISTS vector' -c 'CREATE SCHEMA openviking_v2' >/dev/null
for _ in $(seq 60); do
  docker exec $P-swfs sh -c 'echo "s3.bucket.create -name openviking-v2" | weed shell -master=localhost:9333' 2>/dev/null \
    | grep -qiv error && docker exec $P-swfs sh -c 'echo "s3.bucket.list" | weed shell -master=localhost:9333' 2>/dev/null | grep -q openviking-v2 && break
  sleep 2
done

tree() {
  echo "== bucket openviking-v2, every entry"
  docker exec $P-swfs sh -c 'echo "fs.tree /buckets/openviking-v2" | weed shell -master=localhost:9333' 2>/dev/null
}
start_ov() {  # $1 auth mode
  python3 -I "$D/mkconf.py" "$REPO/deployments/applications/services/openviking/ov.conf.json" "$W/ov.conf" "$1"
  docker rm -f $P-ov >/dev/null 2>&1
  docker volume create $P-data >/dev/null 2>&1
  docker run -d --name $P-ov --network $NET --network-alias ov -v "$W/ov.conf:/secrets/ov.conf:ro" \
    -v $P-data:/app/.openviking \
    -e OPENVIKING_CONFIG_FILE=/secrets/ov.conf -e OPENVIKING_WEB_STUDIO_DIR=/nonexistent \
    -e OV_REFLECT_MODEL=ollama/deepseek-v4.1-flash -e OV_REFLECT_DELTAS_SCHEMA=openviking_v2 \
    -e OV_REFLECT_ENABLED=true -e OV_REFLECT_USER_ID=jasper -e OV_REFLECT_ACCOUNT_ID=lab \
    -e OV_REFLECT_LOCK=process -e OV_REFLECT_INTERVAL_SECONDS=3600 -e OV_REFLECT_DRY_RUN=false \
    -e OV_REFLECT_DELTAS_DSN=postgresql://ov:ov@pg:5432/openviking \
    --entrypoint /app/.venv/bin/python $OV_IMG -m ov_ext --host 0.0.0.0 --port 1933 --with-bot >/dev/null
  for _ in $(seq 150); do
    docker run --rm --network $NET --entrypoint /app/.venv/bin/python $OV_IMG -c \
      'import httpx,sys; sys.exit(0 if httpx.get("http://ov:1933/health",timeout=3).status_code==200 else 1)' \
      >/dev/null 2>&1 && { echo "== ov up ($1)"; return 0; }
    docker inspect -f '{{.State.Running}}' $P-ov | grep -q true || { echo "== ov exited ($1)"; docker logs $P-ov 2>&1 | tail -40; return 1; }
    sleep 2
  done
  echo "== ov never answered /health ($1)"; docker logs $P-ov 2>&1 | tail -40; return 1
}
probe() { docker run --rm --network $NET -v "$D/probe.py:/probe.py:ro" --entrypoint /app/.venv/bin/python $OV_IMG -I /probe.py "$1"; }

trap 'cleanup; docker volume rm $P-data >/dev/null 2>&1' EXIT
docker volume rm $P-data >/dev/null 2>&1
echo "== bucket before first boot"; tree
start_ov oidc || exit 1
echo "== bucket after oidc boot, before any call"; tree
echo "== phase A: OIDC as lab/jasper on empty store"
probe oidc; a=$?
sleep 5
tree | tee "$W/treeA.txt"
echo "== _system files"
uv run -q --no-project --with boto3 python3 -I "$D/keys.py" "http://127.0.0.1:$(docker port $P-swfs 8333/tcp | head -1 | sed 's/.*://')" 2>&1 | tee "$W/keys.txt"
echo "== postgres schemas and tables"
docker exec $P-pg psql -U ov -d openviking -Atc "select table_schema||'.'||table_name from information_schema.tables where table_schema not in ('pg_catalog','information_schema') order by 1"
echo "== ov log warnings/errors (phase A)"
docker logs $P-ov 2>&1 | grep -E 'ERROR|WARN|Traceback|default' | grep -v 'traces' | tail -30

# Top-level account dirs and per-account user dirs anywhere in the key list.
accts=$(grep '^KEY' "$W/keys.txt" | awk '{print $2}' | cut -d/ -f1 | sort -u | tr '\n' ' ')
echo "== top-level prefixes: $accts"
others=$(grep '^KEY' "$W/keys.txt" | awk '{print $2}' | grep -E '(^|/)(default|veerle|hermes)(/|$)' | head)
[ -n "$others" ] && echo "== keys naming another account/user:" && echo "$others"

if [ $a -ne 0 ]; then
  echo "== phase B: api_key boot + root key + POST /admin/accounts, then OIDC again"
  start_ov api_key && probe bootstrap
  start_ov oidc && probe oidc; b=$?
  echo "== phase B oidc probe rc=$b"; tree
  exit 1
fi
# Revised pass condition (plan risk 1 after spike 2): no _system/ key; every
# key outside lab/ is backend_meta.json or a key of the preset default tree
# (directory marker, .abstract.md or .overview.md of default/resources or
# default/user/default/{memories,peers,privacy,resources,sessions,skills}).
keys=$(grep '^KEY' "$W/keys.txt" | awk '{print $2}')
[ -n "$keys" ] || { echo "== FAIL: no keys listed"; exit 1; }
sys=$(echo "$keys" | grep '_system/')
[ -n "$sys" ] && { echo "== FAIL: _system keys:"; echo "$sys"; exit 1; }
preset='^(backend_meta\.json|default/((resources/|user/default/((memories|peers|privacy|resources|sessions|skills)/)?)(\.abstract\.md|\.overview\.md)?)?)$'
bad=$(echo "$keys" | grep -v '^lab/' | grep -Ev "$preset")
[ -n "$bad" ] && { echo "== FAIL: keys outside lab/ beyond the default preset:"; echo "$bad"; exit 1; }
echo "== PASS: $(echo "$keys" | grep -c '^lab/') keys under lab/, $(echo "$keys" | grep -vc '^lab/') preset keys outside it, no _system/"
exit 0
