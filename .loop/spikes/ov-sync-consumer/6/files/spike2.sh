#!/usr/bin/env bash
# Spike ov-sync-consumer risk 1. Local OpenViking v0.4.17.1-9 (SeaweedFS, pgvector,
# OIDC from a local issuer, stub models). As lab/jasper (USER) write files under
# missing folders via content/write and content/batch-write, then delete a file
# and its emptied folder via DELETE /api/v1/fs. drive.py decides the exit.
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1
REPO=$(git rev-parse --show-toplevel)
IMG=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
P=spike-ovc1
NET=$P-net
cleanup() {
  docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1
  docker volume rm $P-data >/dev/null 2>&1
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
docker create --name $P-swfs --network $NET --network-alias swfs chrislusf/seaweedfs:4.48 \
  server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=64 -s3 -s3.port=8333 -s3.config=/s3.json >/dev/null
docker cp "$W/s3.json" $P-swfs:/s3.json; docker start $P-swfs >/dev/null
docker run -d --name $P-pg --network $NET --network-alias pg -e POSTGRES_USER=ov -e POSTGRES_PASSWORD=ov \
  -e POSTGRES_DB=openviking pgvector/pgvector:pg17 >/dev/null
docker run -d --name $P-fake --network $NET --network-alias fake -v "$D/fake.py:/fake.py:ro" \
  --entrypoint /app/.venv/bin/python $IMG -I /fake.py http://fake:8000 >/dev/null
for _ in $(seq 60); do docker exec $P-pg pg_isready -U ov -d openviking >/dev/null 2>&1 && break; sleep 1; done; sleep 2
docker exec $P-pg psql -qU ov -d openviking -c 'CREATE EXTENSION IF NOT EXISTS vector' -c 'CREATE SCHEMA ovp' >/dev/null
for _ in $(seq 30); do
  docker exec $P-swfs sh -c "echo 's3.bucket.create -name ovp' | weed shell -master=localhost:9333" >/dev/null 2>&1
  docker exec $P-swfs sh -c 'echo s3.bucket.list | weed shell -master=localhost:9333' 2>/dev/null | grep -q ovp && break
  sleep 2
done
python3 -I "$D/mkconf.py" "$REPO/deployments/applications/services/openviking/ov.conf.json" "$W/ov.conf" ovp ovp
docker volume create $P-data >/dev/null
docker run -d --name $P-ov --network $NET --network-alias ov -v "$W/ov.conf:/secrets/ov.conf:ro" \
  -v $P-data:/app/.openviking -e OPENVIKING_CONFIG_FILE=/secrets/ov.conf -e OPENVIKING_WEB_STUDIO_DIR=/nonexistent \
  -e OV_REFLECT_ENABLED=false -e OV_REFLECT_DELTAS_SCHEMA=ovp -e OV_REFLECT_DELTAS_DSN=postgresql://ov:ov@pg:5432/openviking \
  -e OV_REFLECT_USER_ID=jasper -e OV_REFLECT_ACCOUNT_ID=lab -e OV_REFLECT_MODEL=stub \
  --entrypoint /app/.venv/bin/python $IMG -m ov_ext --host 0.0.0.0 --port 1933 --with-bot >/dev/null
up=0
for _ in $(seq 150); do
  docker run --rm --network $NET --entrypoint /app/.venv/bin/python $IMG -c \
    'import httpx,sys; sys.exit(0 if httpx.get("http://ov:1933/health",timeout=3).status_code==200 else 1)' \
    >/dev/null 2>&1 && { up=1; break; }
  docker inspect -f '{{.State.Running}}' $P-ov | grep -q true || break
  sleep 2
done
[ $up = 1 ] || { echo "== ov did not come up"; docker logs $P-ov 2>&1 | tail -40; exit 2; }
echo "== ov up"
docker run --rm --network $NET -v "$D/drive2.py:/drive.py:ro" --entrypoint /app/.venv/bin/python $IMG -I /drive.py; rc=$?
echo "== S3 keys under projects/ after the run"
docker exec $P-swfs sh -c 'echo "fs.tree /buckets/ovp" | weed shell -master=localhost:9333' 2>/dev/null | grep -A200 -m1 projects | head -60
echo "== ov log lines about parents/errors"
docker logs $P-ov 2>&1 | grep -E 'ERROR|Traceback|NotFound|not found' | grep -v -e traces -e extract_loop | tail -20
echo "== semantic log lines for w/docs"
docker logs $P-ov 2>&1 | grep -E "projects/w/docs" | tail -30
exit $rc
