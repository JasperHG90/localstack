#!/usr/bin/env bash
# Start SeaweedFS 4.48 in docker, run check.py against it, always remove the container.
set -u
D=$(cd "$(dirname "$0")" && pwd)
C=spike-swfs-bkt-2
docker rm -f $C >/dev/null 2>&1
trap 'docker rm -f $C >/dev/null 2>&1' EXIT
docker run -d --name $C -p 127.0.0.1::8333 -v "$D/s3.json:/etc/s3.json:ro" chrislusf/seaweedfs:4.48 \
  server -dir=/data -s3 -s3.config=/etc/s3.json -s3.iam.readOnly=false -master.volumeSizeLimitMB=32 -volume.max=8 >/dev/null || exit 2
PORT=$(docker port $C 8333 | head -1 | cut -d: -f2)
EP=http://127.0.0.1:$PORT
for i in $(seq 60); do curl -s -o /dev/null "$EP" && break; sleep 1; done
sleep 3
uvx --quiet --with boto3 python "$D/check.py" "$EP"; rc=$?
echo "--- container log tail"; docker logs $C 2>&1 | grep -i -E 'policy|iam|denied|error' | tail -15
exit $rc
