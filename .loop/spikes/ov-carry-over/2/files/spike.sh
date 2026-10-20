#!/usr/bin/env bash
# Spike ov-carry-over risk 2: merge blog-scraper into blogs at the storage level.
# Instance A writes blogs/{src(2),notes(1)} and blog-scraper/{src(2),notes(40),extra(1)}
# under viking://user/jasper/resources; the stub VLM makes the sidecars. Into fresh
# instance B's bucket: blogs keys as-is, then blog-scraper keys remapped to blogs/
# with ignore-existing. On B: POST /content/reindex mode=semantic_and_vectors
# recursive=false on each merged dir, children first, then blogs/; count VLM calls
# per dir. Then vectors_only on blogs. Exit 0 only if the directory regeneration
# makes at most min(direct files, 32)+1 VLM calls per dir (32 = overview_sample_limit),
# the regenerated src and blogs overviews name all 4 src files, vectors_only fails 0,
# B's rows are exactly the expected blogs/ URIs with nothing mentioning blog-scraper,
# no sidecar under blogs/ mentions blog-scraper, and find returns each title.
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmerge
export UV_CACHE_DIR=$D/uvcache
REPO=$(git rev-parse --show-toplevel)
IMG=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
P=spike-ovmerge
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
  -c 'CREATE SCHEMA ovm_a' -c 'CREATE SCHEMA ovm_b' >/dev/null
for b in ovm-a ovm-b; do
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

fail=0
check() { if [ "$2" = 1 ]; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
R=viking://user/jasper/resources

echo "== instance A: bucket ovm-a, schema ovm_a"
docker volume create $P-data-a >/dev/null
boot ovm-a ovm_a $P-data-a || exit 2
drive write >"$W/write.log"; w=$?; grep -c 'HTTP 200' "$W/write.log" | sed 's/^/-- writes with HTTP 200: /'
grep -v 'HTTP 200' "$W/write.log" | head -5
check "A wrote 46 files" "$([ $w = 0 ] && echo 1)"
echo "-- A chat calls so far: $(counts)"
s3 show ovm-a blog-scraper/extra/.overview.md blogs/src/.overview.md
docker rm -f $P-ov >/dev/null

echo "== instance B: fresh bucket ovm-b, empty schema ovm_b"
docker volume create $P-data-b >/dev/null
boot ovm-b ovm_b $P-data-b || exit 2
echo "== merge copy into ovm-b (B running)"
s3 merge ovm-a ovm-b
echo "-- before regeneration:"; s3 show ovm-b blogs/src/.overview.md
s3 grep ovm-b blogs/ blog-scraper

regen() {  # regen URI DIRECT_FILES
  local c0 c1 f o cap
  c0=$(counts); drive sem "$1"; local rc=$?; c1=$(counts)
  f=$(( $(ck "$c1" chat-file) - $(ck "$c0" chat-file) )); o=$(( $(ck "$c1" chat-overview) - $(ck "$c0" chat-overview) ))
  cap=$(( $2 < 32 ? $2 : 32 ))
  echo "VLM $1: $f file-summary calls + $o overview calls (direct files $2, cap $cap+1)"
  TOTAL=$(( TOTAL + f + o ))
  check "sem $1 ok and VLM calls <= $((cap+1))" "$([ $rc = 0 ] && [ $((f+o)) -le $((cap+1)) ] && [ $o -ge 1 ] && echo 1)"
}
TOTAL=0
echo "== phase 1: semantic_and_vectors recursive=false on merged dirs, children first"
regen $R/blogs/src 4
regen $R/blogs/notes 41
regen $R/blogs 0
s3 show ovm-b blogs/src/.overview.md blogs/src/.abstract.md blogs/.overview.md blogs/notes/.abstract.md
ov=$(s3 show ovm-b blogs/src/.overview.md blogs/.overview.md)
for f in alpha-post beta-post gamma-post delta-post; do
  check "blogs/src and blogs overviews both name $f" \
    "$([ "$(grep -o "$f.md" <<<"$ov" | wc -l)" -ge 2 ] && echo 1)"
done
echo "-- sidecars mentioning blog-scraper after regenerating shared dirs:"
s3 grep ovm-b blogs/ blog-scraper | tee "$W/hits"
for d in $(grep '^HIT' "$W/hits" | awk '{print $2}' | sed -E 's#^lab/user/jasper/resources/##; s#/[^/]*$##' | sort -u | awk -F/ '{print NF, $0}' | sort -rn | cut -d' ' -f2); do
  echo "-- regenerating $d too, because its sidecars name blog-scraper"
  regen $R/$d 1
done
echo "VLM TOTAL for directory regeneration: $TOTAL"
s3 grep ovm-b blogs/ blog-scraper >"$W/hits2"; tail -1 "$W/hits2"
check "no sidecar under blogs/ names blog-scraper" "$(grep -q '^0 keys' "$W/hits2" && echo 1)"

echo "== phase 2: vectors_only on blogs"
c0=$(counts); drive vec $R/blogs; vr=$?; c1=$(counts)
dchat=$(( $(ck "$c1" chat) - $(ck "$c0" chat) ))
check "vectors_only failed 0 (VLM calls $dchat)" "$([ $vr = 0 ] && echo 1)"
sleep 5
T=$(tbl ovm_b)
sql "select uri||'|'||level::text from ovm_b.\"$T\" where account_id='lab' and uri like '/user/jasper/resources/%' order by 1" >"$W/rows"
python3 - >"$W/want" <<'PY'
base = "/user/jasper/resources/blogs"
dirs = [base, base + "/src", base + "/notes", base + "/extra"]
files = ["src/alpha-post.md", "src/beta-post.md", "src/gamma-post.md", "src/delta-post.md",
         "notes/blogs-note.md", "extra/epsilon-post.md"] + [f"notes/bulk-{i:02d}.md" for i in range(40)]
rows = [f"{d}|{l}" for d in dirs for l in (0, 1)] + [f"{base}/{f}|2" for f in files]
print("\n".join(sorted(rows)))
PY
echo "-- B rows: $(wc -l <"$W/rows"), expected $(wc -l <"$W/want"); diff (< expected only, > B only):"
diff "$W/want" "$W/rows"
check "B rows are exactly the expected blogs/ uri|level set" "$(diff -q "$W/want" "$W/rows" >/dev/null && echo 1)"
nbs=$(sql "select count(*) from ovm_b.\"$T\" t where t::text like '%blog-scraper%'")
check "no vector row text mentions blog-scraper ($nbs)" "$([ "$nbs" = 0 ] && echo 1)"

drive find; fd=$?
check "find on each title returns its blogs/ file" "$([ $fd = 0 ] && echo 1)"
echo "== B log warnings/errors"
docker logs $P-ov 2>&1 | grep -E 'ERROR|Traceback|reindex|exceeds budget' | grep -v traces | tail -30
exit $fail
