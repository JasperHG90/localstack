#!/usr/bin/env bash
# Spike ov-save-skill risk 2: can a lab/jasper USER token keep a map file at
# viking://user/jasper/resources/.map.md (create, replace, append, read back
# exactly via content/read and the Hermes plugin's viking_read path), and what
# does each write cost in VLM calls and search visibility? Local only: image
# v0.4.17.1-9, SeaweedFS 4.48, pgvector, stub OIDC and models. See drive.py.
set -uo pipefail
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmap
REPO=$(git rev-parse --show-toplevel)
IMG=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
P=spike-ovmap
NET=$P-net
W=$(mktemp -d -p "$D")
cleanup() {
  docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1
  docker volume rm $P-data >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1; rm -rf "$W"
}
trap cleanup EXIT
docker rm -f -v $P-ov $P-fake $P-pg $P-swfs >/dev/null 2>&1; docker volume rm $P-data >/dev/null 2>&1
docker network rm $NET >/dev/null 2>&1
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
docker exec $P-pg psql -qU ov -d openviking -c 'CREATE EXTENSION IF NOT EXISTS vector' -c 'CREATE SCHEMA ovm' >/dev/null
for _ in $(seq 30); do
  docker exec $P-swfs sh -c "echo 's3.bucket.create -name ovm' | weed shell -master=localhost:9333" >/dev/null 2>&1
  docker exec $P-swfs sh -c 'echo s3.bucket.list | weed shell -master=localhost:9333' 2>/dev/null | grep -q ovm && break
  sleep 2
done

python3 -I "$D/mkconf.py" "$REPO/deployments/applications/services/openviking/ov.conf.json" "$W/ov.conf" ovm ovm
docker volume create $P-data >/dev/null
docker run -d --name $P-ov --network $NET --network-alias ov -v "$W/ov.conf:/secrets/ov.conf:ro" \
  -v $P-data:/app/.openviking -e OPENVIKING_CONFIG_FILE=/secrets/ov.conf -e OPENVIKING_WEB_STUDIO_DIR=/nonexistent \
  -e OV_REFLECT_ENABLED=false -e OV_REFLECT_DELTAS_SCHEMA=ovm -e OV_REFLECT_DELTAS_DSN=postgresql://ov:ov@pg:5432/openviking \
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
docker run --rm --network $NET -v "$D/drive.py:/drive.py:ro" --entrypoint /app/.venv/bin/python $IMG -I /drive.py ovm ovm
rc=$?
echo "== ov log warnings/errors"
docker logs $P-ov 2>&1 | grep -E 'ERROR|WARN|Traceback|map\.md' | grep -v traces | tail -30
exit $rc
