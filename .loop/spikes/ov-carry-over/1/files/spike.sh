#!/usr/bin/env bash
# Spike ov-carry-over risk 1. Instance A writes a small tree under
# viking://user/jasper/resources/carry (VLM makes .abstract.md/.overview.md).
# Its S3 keys are copied key for key into the bucket of a fresh instance B
# (empty schema). On B, as lab/jasper with role USER, POST
# /api/v1/content/reindex mode=vectors_only. Exits 0 only if: the copy is
# exact, the reindex reports no failures, the stub saw zero chat (VLM/LLM)
# calls during the reindex, B's vector rows for the tree cover the same URIs
# (and levels) as A's, and find on each file's title returns that file.
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry
export UV_CACHE_DIR=$D/uvcache
REPO=$(git rev-parse --show-toplevel)
IMG=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
P=spike-ovcarry
NET=$P-net
W=$(mktemp -d -p "$D")
cleanup() {
  docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1
  docker volume rm $P-data-a $P-data-b >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1; rm -rf "$W"
}
[ -n "${KEEP:-}" ] || trap cleanup EXIT
cleanup; W=$(mktemp -d -p "$D")
docker network create $NET >/dev/null

cat >"$W/s3.json" <<'J'
{"identities": [{"name": "admin",
  "credentials": [{"accessKey": "SPIKEADMINKEY0000001", "secretKey": "spikeAdminSecret0000000000000000000000001"}],
  "actions": ["Admin", "Read", "Write", "List", "Tagging"]}]}
J
docker create --name $P-swfs --network $NET --network-alias swfs -p 127.0.0.1::8333 chrislusf/seaweedfs:4.48 \
  server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=64 -s3 -s3.port=8333 -s3.config=/s3.json >/dev/null
docker cp "$W/s3.json" $P-swfs:/s3.json; docker start $P-swfs >/dev/null
docker run -d --name $P-pg --network $NET --network-alias pg -e POSTGRES_USER=ov -e POSTGRES_PASSWORD=ov \
  -e POSTGRES_DB=openviking pgvector/pgvector:pg17 >/dev/null
docker run -d --name $P-fake --network $NET --network-alias fake -v "$D/fake.py:/fake.py:ro" \
  --entrypoint /app/.venv/bin/python $IMG -I /fake.py http://fake:8000 >/dev/null
for _ in $(seq 60); do docker exec $P-pg pg_isready -U ov -d openviking >/dev/null 2>&1 && break; sleep 1; done; sleep 2
docker exec $P-pg psql -qU ov -d openviking -c 'CREATE EXTENSION IF NOT EXISTS vector' \
  -c 'CREATE SCHEMA ovc_a' -c 'CREATE SCHEMA ovc_b' >/dev/null
for b in ovc-a ovc-b; do
  for _ in $(seq 30); do
    docker exec $P-swfs sh -c "echo 's3.bucket.create -name $b' | weed shell -master=localhost:9333" >/dev/null 2>&1
    docker exec $P-swfs sh -c 'echo s3.bucket.list | weed shell -master=localhost:9333' 2>/dev/null | grep -q "$b" && break
    sleep 2
  done
done
EP="http://127.0.0.1:$(docker port $P-swfs 8333/tcp | head -1 | sed 's/.*://')"

boot() {  # boot BUCKET SCHEMA VOLUME
  python3 -I "$D/mkconf.py" "$REPO/deployments/applications/services/openviking/ov.conf.json" "$W/ov-$2.conf" "$1" "$2"
  docker rm -f $P-ov >/dev/null 2>&1
  docker run -d --name $P-ov --network $NET --network-alias ov -v "$W/ov-$2.conf:/secrets/ov.conf:ro" \
    -v $3:/app/.openviking -e OPENVIKING_CONFIG_FILE=/secrets/ov.conf -e OPENVIKING_WEB_STUDIO_DIR=/nonexistent \
    -e OV_REFLECT_ENABLED=false -e OV_REFLECT_DELTAS_SCHEMA=$2 -e OV_REFLECT_DELTAS_DSN=postgresql://ov:ov@pg:5432/openviking \
    -e OV_REFLECT_USER_ID=jasper -e OV_REFLECT_ACCOUNT_ID=lab -e OV_REFLECT_MODEL=stub \
    --entrypoint /app/.venv/bin/python $IMG -m ov_ext --host 0.0.0.0 --port 1933 --with-bot >/dev/null
  for _ in $(seq 150); do
    docker run --rm --network $NET --entrypoint /app/.venv/bin/python $IMG -c \
      'import httpx,sys; sys.exit(0 if httpx.get("http://ov:1933/health",timeout=3).status_code==200 else 1)' \
      >/dev/null 2>&1 && { echo "== ov up ($1/$2)"; return 0; }
    docker inspect -f '{{.State.Running}}' $P-ov | grep -q true || break
    sleep 2
  done
  echo "== ov did not come up ($1/$2)"; docker logs $P-ov 2>&1 | tail -40; return 1
}
drive() { docker run --rm --network $NET -v "$D/drive.py:/drive.py:ro" --entrypoint /app/.venv/bin/python $IMG -I /drive.py "$1"; }
counts() { docker run --rm --network $NET --entrypoint /app/.venv/bin/python $IMG -c \
  'import httpx,json; print(json.dumps(httpx.get("http://fake:8080/counts").json(), sort_keys=True))'; }
chats() { python3 -c 'import json,sys; print(sum(v for k,v in json.loads(sys.argv[1]).items() if k.startswith("chat")))' "$1"; }
rows() {  # rows SCHEMA: uri|level for the carry tree in the vector table
  local t; t=$(docker exec $P-pg psql -U ov -d openviking -Atc "select table_name from information_schema.columns where table_schema='$1' and column_name='uri' and table_name not like '%delta%' limit 1")
  local lv; lv=$(docker exec $P-pg psql -U ov -d openviking -Atc "select count(*) from information_schema.columns where table_schema='$1' and table_name='$t' and column_name='level'")
  local col="''"; [ "$lv" = 1 ] && col="level::text"
  docker exec $P-pg psql -U ov -d openviking -Atc "select uri||'|'||coalesce($col,'') from $1.\"$t\" where account_id='lab' and uri like '/user/jasper/resources/carry%' order by 1"
}

fail=0
check() { if [ "$2" = 1 ]; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

echo "== instance A: bucket ovc-a, schema ovc_a"
docker volume create $P-data-a >/dev/null
boot ovc-a ovc_a $P-data-a || exit 2
drive write; w=$?
check "A wrote the tree" "$([ $w = 0 ] && echo 1)"
rows ovc_a >"$W/rows.a"; echo "-- A vector rows for the tree: $(wc -l <"$W/rows.a")"; cat "$W/rows.a"
echo "-- A chat calls so far: $(counts)"
docker logs $P-ov >"$W/log-a.txt" 2>&1; docker rm -f $P-ov >/dev/null

echo "== instance B: fresh bucket ovc-b, empty schema ovc_b, fresh volume"
docker volume create $P-data-b >/dev/null
boot ovc-b ovc_b $P-data-b || exit 2
echo "-- B rows for the tree before copy: $(rows ovc_b | wc -l)"
echo "-- B keys under lab/ before copy:"; docker exec $P-swfs sh -c 'echo "fs.tree /buckets/ovc-b/lab" | weed shell -master=localhost:9333' 2>/dev/null | tail -5
echo "== copy lab/user/jasper/resources/carry/ key for key from ovc-a to ovc-b (B running)"
uv run -q --no-project --with boto3 python3 -I "$D/copy.py" "$EP" ovc-a ovc-b lab/user/jasper/resources/carry/; cp=$?
check "copy exact, with .overview.md sidecars" "$([ $cp = 0 ] && echo 1)"

C0=$(counts); echo "-- stub counts before reindex: $C0"
drive reindex; ri=$?
C1=$(counts); echo "-- stub counts after reindex:  $C1"
check "reindex HTTP 200 with zero failed records" "$([ $ri = 0 ] && echo 1)"
dchat=$(( $(chats "$C1") - $(chats "$C0") ))
check "zero chat (VLM/LLM) calls during reindex (saw $dchat)" "$([ $dchat = 0 ] && echo 1)"
sleep 5
rows ovc_b >"$W/rows.b"; echo "-- B vector rows for the tree: $(wc -l <"$W/rows.b")"; cat "$W/rows.b"
echo "-- rows diff A vs B (< only in A, > only in B):"; diff "$W/rows.a" "$W/rows.b"
check "B indexed every URI/level A had ($(wc -l <"$W/rows.b") of $(wc -l <"$W/rows.a"))" \
  "$([ -s "$W/rows.a" ] && diff -q "$W/rows.a" "$W/rows.b" >/dev/null && echo 1)"

drive find; fd=$?
check "find on each file's title returns that file on B" "$([ $fd = 0 ] && echo 1)"
echo "-- stub counts after find: $(counts)"
echo "== B log warnings/errors"
docker logs $P-ov 2>&1 | grep -E 'ERROR|WARN|Traceback|reindex' | grep -v traces | tail -30
exit $fail
