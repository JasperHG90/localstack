#!/usr/bin/env bash
# Spike seaweedfs-service risk 1: does the pinned arm64 SeaweedFS image run
# all-in-one (weed server -s3) inside a 512 MB memory limit, with S3, a health
# endpoint and Prometheus metrics? Exits 0 only when every check passes.
set -u
IMG=docker.io/chrislusf/seaweedfs:4.48@sha256:f1f303474940e9e088edbd2c1658f7ac38cb0dd90f91a2b0a51916d74b8575a1
NAME=spike-swfs-svc-1
MEM=512m
HERE=$(cd "$(dirname "$0")" && pwd)
fail=0
cleanup() { docker rm -f $NAME >/dev/null 2>&1; }
trap cleanup EXIT
cleanup
echo "host arch: $(uname -m), kernel $(uname -r)"
cat > "$HERE/s3.json" <<'J'
{"identities":[{"name":"admin","credentials":[{"accessKey":"spikeadmin","secretKey":"spikesecret123"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
J
docker create --name $NAME --memory $MEM --memory-swap $MEM \
  -p 127.0.0.1::8333 -p 127.0.0.1::9333 -p 127.0.0.1::8888 -p 127.0.0.1::8080 -p 127.0.0.1::9327 \
  $IMG server -dir=/data -s3 -s3.config=/etc/s3.json \
  -master.volumeSizeLimitMB=64 -volume.max=4 -metricsPort=9327 -ip=127.0.0.1 -ip.bind=0.0.0.0 >/dev/null || exit 2
docker cp "$HERE/s3.json" $NAME:/etc/s3.json || exit 2
docker start $NAME >/dev/null || exit 2
docker image inspect $IMG --format 'image arch: {{.Architecture}} version label: {{index .Config.Labels "org.opencontainers.image.version"}}'
docker exec $NAME weed version
port() { docker port $NAME $1 | head -1 | cut -d: -f2; }
S3=$(port 8333); MA=$(port 9333); FI=$(port 8888); VO=$(port 8080); ME=$(port 9327)
echo "ports: s3=$S3 master=$MA filer=$FI volume=$VO metrics=$ME"
up=0
for i in $(seq 1 60); do
  c=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$S3/ ); [ "$c" != 000 ] && { up=1; echo "S3 port answered HTTP $c after ${i}s"; break; }; sleep 1
done
[ $up = 1 ] || { echo "FAIL: S3 port never answered"; docker logs $NAME 2>&1 | tail -30; exit 1; }
sleep 5
echo "--- health candidates (HTTP code)"
for u in "s3 $S3 /healthz" "s3 $S3 /status" "master $MA /cluster/healthz" "master $MA /cluster/status" "filer $FI /healthz" "volume $VO /healthz" "volume $VO /status"; do
  set -- $u; echo "$1 $3 -> $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$2$3)"
done
echo "--- metrics"
mc=$(curl -s http://127.0.0.1:$ME/metrics | grep -c '^SeaweedFS_')
echo "metrics :9327/metrics SeaweedFS_ series: $mc"
[ "$mc" -gt 0 ] || { echo "FAIL: no metrics"; fail=1; }
curl -s http://127.0.0.1:$ME/metrics | grep -o '^SeaweedFS_[a-z_]*' | sort -u | head -15
mem() { echo "$1: $(docker stats --no-stream --format '{{.MemUsage}}' $NAME) ; cgroup memory.current=$(docker exec $NAME cat /sys/fs/cgroup/memory.current 2>/dev/null) ; weed VmRSS=$(docker exec $NAME sh -c 'grep VmRSS /proc/1/status' | awk '{print $2 $3}')"; }
mem "idle"
echo "--- S3 load (boto3, admin identity)"
uv run --no-project --with boto3 python -I - "$S3" <<'PY' || fail=1
import sys, os, boto3
from botocore.config import Config
s3 = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{sys.argv[1]}", aws_access_key_id="spikeadmin",
    aws_secret_access_key="spikesecret123", region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))
s3.create_bucket(Bucket="spike")
blobs = {f"obj{i}": os.urandom(256 * 1024 * (1 + i % 4)) for i in range(40)}
for k, v in blobs.items(): s3.put_object(Bucket="spike", Key=k, Body=v)
for k, v in blobs.items(): assert s3.get_object(Bucket="spike", Key=k)["Body"].read() == v, k
n = s3.list_objects_v2(Bucket="spike")["KeyCount"]
print(f"put+get {len(blobs)} objects ({sum(map(len, blobs.values()))//1024//1024} MiB), list KeyCount={n}")
assert n == 40
try:
    boto3.client("s3", endpoint_url=f"http://127.0.0.1:{sys.argv[1]}", aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1").list_buckets()
    print("WARN: wrong key was accepted")
except Exception as e: print("wrong key refused:", type(e).__name__, getattr(e, "response", {}).get("Error", {}).get("Code"))
for k in blobs: s3.delete_object(Bucket="spike", Key=k)
s3.delete_bucket(Bucket="spike")
print("delete objects + bucket ok")
PY
mem "after load"
sleep 15
mem "15s after load"
st=$(docker inspect $NAME --format '{{.State.Status}} oom={{.State.OOMKilled}} restarts={{.RestartCount}}')
echo "state: $st"
case "$st" in running*oom=false*) ;; *) fail=1;; esac
docker logs $NAME 2>&1 | grep -iE 'panic|fatal|error' | head -5
exit $fail
