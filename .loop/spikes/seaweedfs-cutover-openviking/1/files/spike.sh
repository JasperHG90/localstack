#!/usr/bin/env bash
# Spike: does OpenViking's own AGFS s3fs backend (Rust, from the deployed
# image) work against SeaweedFS 4.48 with path-style requests and a static
# IAM key scoped to bucket openviking? Exits 0 only if every op passes.
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
IMG=chrislusf/seaweedfs:4.48
OV=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
NAME=spike-swfs-ov-1
NET=spike-swfs-ov-1-net
W=$(mktemp -d)
trap 'docker rm -f -v "$NAME" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; rm -rf "$W"' EXIT
cat >"$W/s3.json" <<'J'
{"identities": [{"name": "admin",
  "credentials": [{"accessKey": "SPIKEADMINKEY0000001", "secretKey": "spikeAdminSecret0000000000000000000000001"}],
  "actions": ["Admin", "Read", "Write", "List", "Tagging"]}]}
J
docker rm -f -v "$NAME" >/dev/null 2>&1 || true
docker network rm "$NET" >/dev/null 2>&1 || true
docker network create "$NET" >/dev/null
docker create --name "$NAME" --network "$NET" -p 127.0.0.1::8333 "$IMG" \
  server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=64 \
  -s3 -s3.port=8333 -s3.config=/s3.json -s3.iam.readOnly=false >/dev/null
docker cp "$W/s3.json" "$NAME:/s3.json"
docker start "$NAME" >/dev/null
PORT=$(docker port "$NAME" 8333/tcp | head -1 | sed 's/.*://')
for _ in $(seq 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)
  [ "$code" != "000" ] && [ "$code" != "503" ] && break
  sleep 1
done
sleep 3
read -r AK SK < <(uv run -q --no-project --with boto3 python3 -I "$D/iam.py" "$PORT")
echo "openviking IAM user key: $AK"
sleep 2
rc=0
docker run --rm --network "$NET" -v "$D/ov_probe.py:/probe.py:ro" --entrypoint /app/.venv/bin/python \
  "$OV" -I /probe.py "$AK" "$SK" "http://$NAME:8333" || rc=$?
echo "== objects in bucket openviking (admin view)"
docker exec "$NAME" sh -c 'echo "fs.ls -l /buckets/openviking" | weed shell -master=localhost:9333 2>/dev/null' | tail -20 || true
echo "== seaweedfs log errors"
docker logs "$NAME" 2>&1 | grep -iE 'error|denied|unsupported|not implemented' | tail -20 || true
echo "probe rc=$rc"
exit $rc
