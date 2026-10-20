#!/usr/bin/env bash
# Spike (ov-fresh-instance risk 2): does pointing OpenViking (ov-postgres and
# ov-ext reflection) at schema openviking_v2 leave schema openviking and
# schema public untouched in the same database? Exits 0 only if every check holds.
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovschema
OV=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
NET=ovsch-net
DSN=postgresql://openviking:ovpw@ovsch-pg:5432/openviking
W=$(mktemp -d)
cleanup() {
  docker rm -f -v ovsch-pg ovsch-s3 ovsch-stub ovsch-ov >/dev/null 2>&1
  docker volume rm ovsch-ws1 ovsch-ws2 >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1
  rm -rf "$W"
}
trap cleanup EXIT
cleanup; W=$(mktemp -d)
docker network create $NET >/dev/null
docker volume create ovsch-ws1 >/dev/null; docker volume create ovsch-ws2 >/dev/null

psql_su() { docker exec -i ovsch-pg psql -U postgres -d openviking -v ON_ERROR_STOP=1 -qAt "$@"; }

echo "== start postgres (pgvector pg17), seaweedfs 4.48, stub model server"
docker run -d --name ovsch-pg --network $NET -e POSTGRES_PASSWORD=su pgvector/pgvector:pg17 >/dev/null
cat >"$W/s3.json" <<'J'
{"identities": [{"name": "admin", "credentials": [{"accessKey": "SPIKEADMINKEY0000001",
 "secretKey": "spikeAdminSecret0000000000000000000000001"}], "actions": ["Admin","Read","Write","List","Tagging"]}]}
J
docker create --name ovsch-s3 --network $NET chrislusf/seaweedfs:4.48 server -dir=/data -ip.bind=0.0.0.0 \
  -master.volumeSizeLimitMB=64 -s3 -s3.port=8333 -s3.config=/s3.json >/dev/null
docker cp "$W/s3.json" ovsch-s3:/s3.json; docker start ovsch-s3 >/dev/null
docker run -d --name ovsch-stub --network $NET -v "$D/stub.py:/stub.py:ro" --entrypoint /app/.venv/bin/python $OV -I /stub.py >/dev/null
for _ in $(seq 60); do docker exec ovsch-pg pg_isready -U postgres -q 2>/dev/null && break; sleep 1; done; sleep 2
# Same shape as prod: role openviking owns database openviking, vector made by the superuser.
docker exec -i ovsch-pg psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
CREATE ROLE openviking LOGIN PASSWORD 'ovpw';
CREATE DATABASE openviking OWNER openviking;
\c openviking
CREATE EXTENSION vector;
SQL
for b in openviking openviking-v2; do
  for _ in $(seq 30); do docker exec ovsch-s3 sh -c "echo 's3.bucket.create -name $b' | weed shell -master=localhost:9333" 2>&1 | grep -qi error || break; sleep 2; done
done

boot() { # boot SCHEMA BUCKET VOLUME LABEL
  sed -e "s|__BUCKET__|$2|" -e "s|__SCHEMA__|$1|" -e "s|__DSN__|$DSN|" "$D/ov.conf.tmpl" >"$W/ov-$4.conf"
  docker create --name ovsch-ov --network $NET -v "$3:/app/.openviking" \
    -e OPENVIKING_CONFIG_FILE=/ov.conf -e OPENVIKING_WEB_STUDIO_DIR=/nonexistent \
    -e OV_REFLECT_ENABLED=true -e OV_REFLECT_MODEL=stub -e OV_REFLECT_DELTAS_SCHEMA="$1" \
    -e OV_REFLECT_DELTAS_DSN="$DSN" -e OV_REFLECT_USER_ID=jasper -e OV_REFLECT_ACCOUNT_ID=lab \
    -e OV_REFLECT_LOCK=process -e OV_REFLECT_INTERVAL_SECONDS=3600 -e OV_REFLECT_DRY_RUN=false \
    -e OV_REFLECT_BATCH_LIMIT=20 \
    --entrypoint /app/.venv/bin/python $OV -m ov_ext --host 127.0.0.1 --port 1933 --with-bot >/dev/null
  docker cp "$W/ov-$4.conf" ovsch-ov:/ov.conf; docker cp "$D/drive.py" ovsch-ov:/drive.py
  docker start ovsch-ov >/dev/null
  for i in $(seq 300); do
    docker exec ovsch-ov /app/.venv/bin/python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:1933/health',timeout=3)" >/dev/null 2>&1 && { echo "[$4] /health up after ${i}s"; return 0; }
    sleep 1
  done
  echo "[$4] never came up"; docker logs ovsch-ov 2>&1 | tail -40; return 1
}
wait_sweep() { for _ in $(seq 120); do docker logs ovsch-ov 2>&1 | grep -q 'ov-ext reflect: batches=' && break; sleep 1; done
  echo "[$1] sweep log: $(docker logs ovsch-ov 2>&1 | grep -E 'ov-ext reflect: (batches=|reading changes|could not open|sweep failed)' | sed 's/^.*ov-ext/ov-ext/' | tr '\n' '|' )"; }
stop() { docker logs ovsch-ov >"$W/log-$1.txt" 2>&1; docker rm -f ovsch-ov >/dev/null; sleep 3; }

snap() { # stats only (reads and writes on schema openviking)
  psql_su -c "select relname,n_tup_ins,n_tup_upd,n_tup_del,coalesce(seq_scan,0),coalesce(idx_scan,0) from pg_stat_user_tables where schemaname='openviking' order by 1"; }
# pg_dump 17.6+ writes a random \restrict token per run; drop it so equal data hashes equal.
dumph() { docker exec ovsch-pg pg_dump -U postgres -d openviking --schema=openviking | grep -v -E '^\\(un)?restrict ' >"$W/dump.$1"; sha256sum <"$W/dump.$1" | cut -c1-16; }
publ() { psql_su -c "select 'rel:'||relname||':'||relkind::text from pg_class where relnamespace='public'::regnamespace union all
  select 'proc:'||proname from pg_proc where pronamespace='public'::regnamespace union all
  select 'type:'||typname from pg_type where typnamespace='public'::regnamespace union all
  select 'schema:'||nspname from pg_namespace order by 1"; }

echo "== phase 1: old instance on schema openviking, bucket openviking"
boot openviking openviking ovsch-ws1 p1 || exit 2
docker exec ovsch-ov /app/.venv/bin/python /drive.py p1 openviking "$DSN"
wait_sweep p1
stop p1
echo "-- schema openviking after phase 1:"; snap
publ >"$W/public.before"
snap >"$W/stats.A"; H1=$(dumph before); snap >"$W/stats.B"
echo "baseline dump hash: $H1"; echo "public/schema objects before: $(wc -l <"$W/public.before")"

echo "== phase 2: new instance on schema openviking_v2, bucket openviking-v2, fresh volume"
boot openviking_v2 openviking-v2 ovsch-ws2 p2a || exit 2
echo "[p2a] delta store log: $(docker logs ovsch-ov 2>&1 | grep -E 'ov-ext reflect: (reading changes|could not open)' | sed 's/^.*ov-ext/ov-ext/' | head -2 | tr '\n' '|')"
FIRST_BOOT_DELTAS_OK=0
docker logs ovsch-ov 2>&1 | grep -q 'reading changes from openviking_v2' && FIRST_BOOT_DELTAS_OK=1
docker exec ovsch-ov /app/.venv/bin/python /drive.py p2 openviking_v2 "$DSN"
wait_sweep p2a
stop p2a
echo "== phase 2 restart (second boot, sweep reads the recorded deltas)"
boot openviking_v2 openviking-v2 ovsch-ws2 p2b || exit 2
wait_sweep p2b
stop p2b

snap >"$W/stats.C"; H2=$(dumph after); publ >"$W/public.after"
echo "-- schema openviking_v2 tables:"
psql_su -c "select relname,n_tup_ins,n_tup_upd,n_tup_del from pg_stat_user_tables where schemaname='openviking_v2' order by 1"
echo "-- openviking_v2.ov_memory_deltas rows: $(psql_su -c "select count(*)||' (reflected '||count(reflected_at)||')' from openviking_v2.ov_memory_deltas" 2>&1)"
echo "-- openviking.memory_deltas rows: $(psql_su -c "select count(*)||' uris like p2: '||count(*) filter (where uri like '%p2%') from openviking.ov_memory_deltas" 2>&1)"
echo "-- schema openviking stats diff (B baseline vs C after), empty means equal:"; diff "$W/stats.B" "$W/stats.C"
echo "-- public/schema objects diff, empty means equal:"; diff "$W/public.before" "$W/public.after"
echo "after dump hash: $H2 (dump lines: $(wc -l <"$W/dump.after"))"; diff "$W/dump.before" "$W/dump.after" | head -20

fail=0
check() { if [ "$2" = 1 ]; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
V2=$(psql_su -c "select count(*) from pg_tables where schemaname='openviking_v2'")
check "schema openviking_v2 created with tables ($V2)" "$([ "$V2" -gt 0 ] && echo 1)"
check "schema openviking tuple and scan counters unchanged" "$(diff -q "$W/stats.B" "$W/stats.C" >/dev/null && echo 1)"
check "schema openviking pg_dump hash unchanged" "$([ "$H1" = "$H2" ] && echo 1)"
check "nothing new in public or new schemas besides openviking_v2" "$(diff "$W/public.before" "$W/public.after" | grep '^>' | grep -v 'schema:openviking_v2' | grep -q . || echo 1)"
# Reported, not gating: it degrades reflection on the new schema until a
# restart but touches neither the old schema nor public.
if [ "$FIRST_BOOT_DELTAS_OK" = 1 ]; then echo "FINDING ov-ext delta store opened on openviking_v2 at first boot";
else echo "FINDING ov-ext delta store did NOT open on openviking_v2 at first boot (schema not yet created); opened after restart: $(grep -c 'reading changes from openviking_v2' "$W/log-p2b.txt")"; fi
echo "== log errors mentioning schema/relation (all phases)"
grep -h -i -E 'relation .* does not exist|schema .* does not exist|permission denied' "$W"/log-*.txt | sed 's/^.*\(ERROR\|error\)/\1/' | sort | uniq -c | head -20
exit $fail
