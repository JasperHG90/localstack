#!/usr/bin/env bash
# Spike: do six buckets each take a write on one `weed server`, does a 300 MB
# write fit, and can master/volume/filer bind loopback while S3 and metrics
# answer off-host? Phase A runs defaults and only reports. Phase B runs the
# candidate flag set and is the gate: exit 0 only if it passes.
set -uo pipefail
IMG=chrislusf/seaweedfs:4.48
NAME=spike-swfs-svc-3
NET=spike-swfs-svc-3-net
VOL=spike-swfs-svc-3-data
W=$(mktemp -d)
cleanup() { docker rm -f -v "$NAME" >/dev/null 2>&1; docker volume rm "$VOL" >/dev/null 2>&1; docker network rm "$NET" >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
cat >"$W/s3.json" <<'J'
{"identities":[{"name":"admin","credentials":[{"accessKey":"SPIKEADMINKEY0000001","secretKey":"spikeAdminSecret0000000000000000000000001"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
J
cat >"$W/probe.py" <<'P'
import sys, io, boto3
from botocore.config import Config
port, big = sys.argv[1], int(sys.argv[2])
s3 = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{port}",
    aws_access_key_id="SPIKEADMINKEY0000001",
    aws_secret_access_key="spikeAdminSecret0000000000000000000000001",
    region_name="us-east-1", config=Config(retries={"max_attempts": 1}, s3={"addressing_style": "path"}))
ok = 0
for b in ["registry", "models", "datalake", "openviking", "loki", "tempo"]:
    try:
        s3.create_bucket(Bucket=b); s3.put_object(Bucket=b, Key="o.txt", Body=b"hello " + b.encode())
        assert s3.get_object(Bucket=b, Key="o.txt")["Body"].read() == b"hello " + b.encode()
        print(f"PASS bucket {b}: write+read"); ok += 1
    except Exception as e:
        print(f"FAIL bucket {b}: {type(e).__name__}: {str(e)[:300]}")
big_ok = True
if big:
    try:
        chunk = bytes(range(256)) * 4096 * 100  # 100 MiB
        for i in range(3):
            s3.upload_fileobj(io.BytesIO(chunk), "registry", f"big{i}.bin")
        n = sum(o["Size"] for o in s3.list_objects_v2(Bucket="registry", Prefix="big")["Contents"])
        print(f"PASS 300 MiB into registry: {n} bytes listed")
    except Exception as e:
        big_ok = False; print(f"FAIL 300 MiB write: {type(e).__name__}: {str(e)[:300]}")
print(f"RESULT buckets_ok={ok}/6 big_ok={big_ok}")
sys.exit(0 if ok == 6 and big_ok else 1)
P

run_phase() {  # $1 label, $2 big(0/1), rest: weed server flags
  local label=$1 big=$2; shift 2
  echo; echo "===== phase $label: weed server $*"
  cleanup; W=$(mktemp -d)
  docker network create "$NET" >/dev/null; docker volume create "$VOL" >/dev/null
  docker create --name "$NAME" --network "$NET" -v "$VOL:/data" -p 127.0.0.1::8333 "$IMG" \
    server -dir=/data -s3 -s3.port=8333 -s3.config=/s3.json "$@" >/dev/null
  docker cp "$S3JSON" "$NAME:/s3.json"
  [ -n "${MASTER_TOML:-}" ] && { printf '%s\n' "$MASTER_TOML" >"$KEEP/master.toml"; docker cp "$KEEP/master.toml" "$NAME:/etc/seaweedfs/master.toml"; echo "master.toml: $MASTER_TOML"; }
  docker start "$NAME" >/dev/null
  PORT=$(docker port "$NAME" 8333/tcp | head -1 | sed 's/.*://')
  for _ in $(seq 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz")" = 200 ] && break; sleep 1; done
  sleep 3
  rc=0; uv run -q --no-project --with boto3 python3 -I "$PYF" "$PORT" "$big" || rc=$?
  echo "-- master /vol/status (slots)"
  docker exec "$NAME" wget -qO- http://127.0.0.1:9333/vol/status 2>/dev/null | python3 -c '
import json,sys; d=json.load(sys.stdin)["Volumes"]
print("Max", d.get("Max"), "Free", d.get("Free"))
cols={}
def walk(x):
    if isinstance(x,dict):
        if "Collection" in x and "Id" in x: cols.setdefault(x["Collection"] or "(default)",[]).append(x["Id"])
        else: [walk(v) for v in x.values()]
    elif isinstance(x,list): [walk(v) for v in x]
walk(d); print("volumes per collection:", {k:len(v) for k,v in cols.items()})' || echo "(vol/status unreadable)"
  docker exec "$NAME" wget -qO- http://127.0.0.1:9333/dir/status 2>/dev/null | python3 -c '
import json,sys; t=json.load(sys.stdin)["Topology"]; print("dir/status Max", t.get("Max"), "Free", t.get("Free"))' || true
  docker logs "$NAME" 2>&1 | grep -iE 'no free|not enough|no writable|grow' | sort | uniq -c | head -8
  echo "-- data dir size"; docker exec "$NAME" du -sh /data
  PHASE_RC=$rc
}
S3JSON="$W/s3.json.keep"; cp "$W/s3.json" "$S3JSON"; PYF="$W/probe.keep.py"; cp "$W/probe.py" "$PYF"
KEEP=$(mktemp -d); cp "$S3JSON" "$PYF" "$KEEP/"; S3JSON="$KEEP/s3.json.keep"; PYF="$KEEP/probe.keep.py"
trap 'cleanup; rm -rf "$KEEP"' EXIT

run_phase A-defaults 0 -ip.bind=0.0.0.0
A_RC=$PHASE_RC

FLAGS=(-ip=127.0.0.1 -ip.bind=127.0.0.1 -s3.ip.bind=0.0.0.0 -metricsIp=0.0.0.0 -metricsPort=9327
       -volume.max=0 -master.volumeSizeLimitMB=1024 -master.volumePreallocate=false
       -s3.port.iceberg=0 -s3.port.lance=0 -s3.iam.readOnly=false)
MASTER_TOML=$'[master.volume_growth]\ncopy_1 = 2'
run_phase B-candidate 1 "${FLAGS[@]}"
B_RC=$PHASE_RC

echo "-- listeners inside container (B)"
docker exec "$NAME" netstat -tln 2>/dev/null | awk 'NR>2{print $4}' | sort -u | tr '\n' ' '; echo
echo "-- ports reachable from another container on $NET (B)"
PORTS="8333 18333 9327 9333 19333 8080 18080 8888 18888 8111 6060 8181 9101 7333 2022 17777 16777"
OPEN=$(docker run --rm --network "$NET" --entrypoint sh "$IMG" -c "for p in $PORTS; do nc -z -w2 $NAME \$p 2>/dev/null && echo \$p; done" | tr '\n' ' ')
echo "open: $OPEN"
echo "metrics series: $(docker run --rm --network "$NET" --entrypoint sh "$IMG" -c "wget -qO- http://$NAME:9327/metrics | grep -c ^SeaweedFS_")"
BIND_OK=1
# 18333 is the S3 gRPC port. It follows -s3.ip.bind and has no flag of its
# own (-s3.port.grpc=-1 is fatal), so the firewall, not the bind, must close it.
for p in $OPEN; do case $p in 8333|9327|18333) ;; *) BIND_OK=0; echo "UNEXPECTED off-host port $p";; esac; done
case " $OPEN " in *" 8333 "*) ;; *) BIND_OK=0; echo "S3 not reachable off-host";; esac
case " $OPEN " in *" 9327 "*) ;; *) BIND_OK=0; echo "metrics not reachable off-host";; esac

echo; echo "SUMMARY A(defaults) rc=$A_RC  B(candidate) rc=$B_RC bind_ok=$BIND_OK"
echo "FLAGS: ${FLAGS[*]}"; echo "master.toml: $MASTER_TOML"
[ "$B_RC" = 0 ] && [ "$BIND_OK" = 1 ]
