#!/usr/bin/env bash
# Spike ov-carry-over p2: do images survive a key-for-key carry-over?
# Instance A ingests a .png through temp_upload + add_resource (ov-clip's path) into
# clips/pelican-clip, then writes a .md beside it; the stub VLM writes overviews in the
# real "### [name](viking://...)" format seen in the old bucket. All clips keys go key
# for key into fresh B. On B: vectors_only on clips, then, while the png has no L2 row
# or find misses it, try in turn: semantic_and_vectors recursive=false on the image dir
# followed by vectors_only on it; semantic_and_vectors recursive=true on the dir;
# semantic_and_vectors on the png URI. Count VLM calls per step by kind.
# Steps 5 and 6 try, for a second image (heron-clip), add_resource again to the same dir, and
# for the pelican png, copying its old L2 row from the source schema. Exit 0 only if some
# step leaves an L2 row for the png that find returns itself, at a bounded
# VLM cost (at most 1 image call per image plus 1 overview call per directory).
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg
export UV_CACHE_DIR=$D/uvcache
REPO=$(git rev-parse --show-toplevel)
IMG=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
P=spike-ovimg
NET=$P-net
cleanup() {
  docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1
  docker volume rm $P-data-a $P-data-b >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1; rm -rf "${W:-/nonexistent}"
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
  -c 'CREATE SCHEMA ovi_a' -c 'CREATE SCHEMA ovi_b' >/dev/null
for b in ovi-a ovi-b; do
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
drive() { docker run --rm --network $NET -v "$D/drive.py:/drive.py:ro" --entrypoint /app/.venv/bin/python $IMG -I /drive.py "$@"; }
s3() { uv run -q --no-project --with boto3 python3 -I "$D/s3tool.py" "$1" "$EP" "${@:2}"; }
counts() { docker run --rm --network $NET --entrypoint /app/.venv/bin/python $IMG -c \
  'import httpx,json; print(json.dumps(httpx.get("http://fake:8080/counts").json(), sort_keys=True))'; }
ck() { python3 -c 'import json,sys; print(sum(v for k,v in json.loads(sys.argv[1]).items() if k.startswith(sys.argv[2])))' "$1" "$2"; }
tbl() { docker exec $P-pg psql -U ov -d openviking -Atc "select table_name from information_schema.columns where table_schema='$1' and column_name='uri' and table_name not like '%delta%' limit 1"; }
sql() { docker exec $P-pg psql -U ov -d openviking -Atc "$1"; }
delta() {  # delta BEFORE AFTER -> "image I, file F, overview O"
  echo "image $(( $(ck "$2" chat-image) - $(ck "$1" chat-image) )), file $(( $(ck "$2" chat-file) - $(ck "$1" chat-file) )), overview $(( $(ck "$2" chat-overview) - $(ck "$1" chat-overview) ))"
}

R=viking://user/jasper/resources
PEL=/user/jasper/resources/clips/pelican-clip/pelican-diagram.png
HER=/user/jasper/resources/clips/heron-clip/heron-photo.png
abs_of() { sql "select abstract from $1.\"$2\" where uri='$3' and level=2"; }

echo "== instance A: bucket ovi-a, schema ovi_a"
docker volume create $P-data-a >/dev/null
boot ovi-a ovi_a $P-data-a || exit 2
c0=$(counts)
drive ingest pelican-diagram pelican-clip 32 pelican-notes.md | grep -E 'HTTP [45]'
drive ingest heron-photo heron-clip 24 | grep -E 'HTTP [45]'
c1=$(counts); echo "-- A ingest VLM: $(delta "$c0" "$c1")"
s3 show ovi-a clips/pelican-clip/.overview.md clips/heron-clip/.overview.md | grep -E '^(-----|###)|^The image'
TA=$(tbl ovi_a)
echo "-- A rows under clips/:"; sql "select uri||'|'||level::text from ovi_a.\"$TA\" where uri like '/user/jasper/resources/clips/%' order by 1"
QP=$(abs_of ovi_a "$TA" "$PEL"); QH=$(abs_of ovi_a "$TA" "$HER")
echo "-- queries: pelican [$QP] heron [$QH]"
drive find "$QP" "$PEL" | grep -E '^(PASS|FAIL)'; drive find "$QH" "$HER" | grep -E '^(PASS|FAIL)'
docker rm -f $P-ov >/dev/null

echo "== instance B: fresh bucket ovi-b, empty schema ovi_b"
docker volume create $P-data-b >/dev/null
boot ovi-b ovi_b $P-data-b || exit 2
s3 copy ovi-a ovi-b clips/
TB=""
state() {  # state LABEL PATH QUERY -> HAS=1 when PATH has an L2 row and find returns PATH itself
  sleep 4; [ -n "$TB" ] || TB=$(tbl ovi_b)
  local row; row=$(sql "select count(*) from ovi_b.\"$TB\" where uri='$2' and level=2")
  drive find "$3" "$2" >/dev/null; local f=$?
  echo "-- after $1: ${2##*/} L2 rows $row, find returns the file: $([ $f = 0 ] && echo yes || echo no)"
  HAS=$([ "$row" -ge 1 ] && [ $f = 0 ] && echo 1 || echo 0)
}
WORKS=""
step() {  # step LABEL PATH QUERY CMD...
  local c0 c1; c0=$(counts); "${@:4}" | grep -E '^RESULT|HTTP [45]'; c1=$(counts)
  echo "-- $1 VLM: $(delta "$c0" "$c1")"
  state "$1" "$2" "$3"
  if [ "$HAS" = 1 ]; then WORKS="$WORKS
  $1 ($(delta "$c0" "$c1"))"; fi
}
step "1 vectors_only on clips" "$PEL" "$QP" drive vec $R/clips
state "1 (heron)" "$HER" "$QH"
step "2a semantic_and_vectors recursive=false on pelican dir" "$PEL" "$QP" drive sem $R/clips/pelican-clip false
step "2b vectors_only on pelican dir after 2a" "$PEL" "$QP" drive vec $R/clips/pelican-clip
step "3 semantic_and_vectors recursive=true on pelican dir" "$PEL" "$QP" drive sem $R/clips/pelican-clip true
step "4 semantic_and_vectors on the pelican png URI" "$PEL" "$QP" drive sem "$R/clips/pelican-clip/pelican-diagram.png" false
step "5 add_resource the heron png again to the same dir" "$HER" "$QH" drive readd heron-photo heron-clip 24
s3 show ovi-b clips/heron-clip/.overview.md | grep -E '^(-----|###)|^The image'
TB=$(tbl ovi_b)
cols=$(sql "select string_agg(quote_ident(column_name), ',' order by ordinal_position) from information_schema.columns where table_schema='ovi_b' and table_name='$TB'")
c0=$(counts)
sql "insert into ovi_b.\"$TB\" ($cols) select $cols from ovi_a.\"$TA\" where uri='$PEL' and level=2 on conflict do nothing" >/dev/null
sql "select 'copied L2 rows for pelican png: '||count(*) from ovi_b.\"$TB\" where uri='$PEL' and level=2"
step "6 copy the old L2 row for the pelican png, then vectors_only on its dir" "$PEL" "$QP" drive vec $R/clips/pelican-clip
echo "-- 6 VLM since the row copy: $(delta "$c0" "$(counts)")"
echo "-- B rows under clips/:"; sql "select uri||'|'||level::text from ovi_b.\"$TB\" where uri like '/user/jasper/resources/clips/%' order by 1"
echo "== B log lines"
docker logs $P-ov 2>&1 | grep -E 'ERROR|Traceback|No vector source' | grep -v traces | tail -15
if [ -n "$WORKS" ]; then echo "STEPS THAT MADE AN IMAGE SEARCHABLE:$WORKS"; exit 0; fi
echo "NO STEP MADE AN IMAGE SEARCHABLE"; exit 1
