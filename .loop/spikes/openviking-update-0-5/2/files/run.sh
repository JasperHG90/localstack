#!/usr/bin/env bash
# First boot of ov-postgres 0.7.0 / OpenViking 0.5.6 on a table seeded by
# ov-postgres 0.6.0 / OpenViking 0.4.17.1. Exits 0 only when the reconcile and
# the md5 backfill both fit the openviking job's limits (see the check below).
set -euo pipefail
HERE=/home/vscode/spike-scratch/ov-boot
ROWS=${ROWS:-50000}
DIM=384
OLD_PY=$HOME/.cache/ov-postgres-tests/ov-postgres-v0.6.0-openviking-0.4.17.1/bin/python
NEW_PY=$HERE/new-venv/bin/python
NAME=ov-boot-spike-$$
WS=$(mktemp -d)
CONF=$(mktemp); echo '{}' > "$CONF"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$WS" "$CONF"; }
trap cleanup EXIT

docker run -d --name "$NAME" --cpus=1 -e POSTGRES_PASSWORD=spike -p 127.0.0.1::5432 pgvector/pgvector:pg17 >/dev/null
for _ in $(seq 60); do docker exec "$NAME" pg_isready -U postgres -q && break; sleep 1; done
sleep 2
docker exec "$NAME" psql -q -U postgres -c "CREATE ROLE openviking LOGIN PASSWORD 'spike'" \
  -c "CREATE DATABASE openviking OWNER openviking"
docker exec "$NAME" psql -q -U postgres -d openviking -c "CREATE EXTENSION vector" \
  -c "CREATE SCHEMA openviking_v2 AUTHORIZATION openviking"
PORT=$(docker port "$NAME" 5432/tcp | head -1 | cut -d: -f2)
DSN="postgresql://openviking:spike@127.0.0.1:$PORT/openviking"
echo "postgres cpus: $(docker inspect -f '{{.HostConfig.NanoCpus}}' "$NAME") nano"

SEED=$(env -u PYTHONPATH "$OLD_PY" -I "$HERE/seed_old.py" "{\"dsn\":\"$DSN\",\"schema\":\"openviking_v2\",\"rows\":$ROWS,\"dim\":$DIM}" 2>/dev/null | tail -1)
echo "seed: $SEED"
DIRS=$(echo "$SEED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["dirs"])')
docker exec "$NAME" psql -tA -U postgres -d openviking -c \
  "SELECT 'table size before: ' || pg_size_pretty(pg_total_relation_size('openviking_v2.ov_context'))"

OUT=$(OPENVIKING_CONFIG_FILE=$CONF taskset -c 2 "$NEW_PY" -I "$HERE/boot_new.py" \
  "{\"dsn\":\"$DSN\",\"schema\":\"openviking_v2\",\"dim\":$DIM,\"dirs\":$DIRS,\"workspace\":\"$WS\"}" 2>"$WS.err") \
  || { tail -40 "$WS.err" >&2; exit 2; }
grep -E 'reconcile|added|backfill done' "$WS.err" | tail -5 || true
rm -f "$WS.err"
echo "$OUT"
docker exec "$NAME" psql -tA -U postgres -d openviking -c \
  "SELECT 'md5 filled: ' || count(*) FILTER (WHERE md5 <> '') || ' of ' || count(*) FROM openviking_v2.ov_context" \
  -c "SELECT 'acl indexes: ' || string_agg(indexname, ', ') FROM pg_indexes WHERE schemaname='openviking_v2' AND indexdef ~ 'acl_'" \
  -c "SELECT 'table size after: ' || pg_size_pretty(pg_total_relation_size('openviking_v2.ov_context'))"

# openviking.hcl: healthy_deadline 60m; the alive check times out at 5s.
# Pass when the reconcile takes under a tenth of the deadline (360 s), the
# event loop never stalls near the 5 s check timeout during the backfill, and
# a concurrent vector query stays under 1 s at p95 during it.
echo "$OUT" | sed -n 's/^REPORT //p' | python3 -c '
import json, sys
r = json.load(sys.stdin)
checks = {
    "reconcile under 360s": r["reconcile_s"] < 360,
    "backfill filled every row": r["backfill_filled"] == r["rows"] and not r["backfill_pending_after"],
    "loop lag max under 1s during backfill": r["loop_lag_during"]["max"] < 1.0,
    "query p95 under 1s during backfill": r["query_during"]["p95"] < 1.0,
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
sys.exit(0 if all(checks.values()) else 1)
'
