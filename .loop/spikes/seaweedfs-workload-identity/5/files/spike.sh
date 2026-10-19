#!/usr/bin/env bash
# One weed server with the static admin (-s3.config), the writable embedded IAM
# (-s3.iam.readOnly=false), and the OIDC/STS IAM file (-s3.iam.config with
# defaultEffect Deny), plus the production slot flags and master.toml. Checks
# admin, Terraform-made user and STS role, before and after a restart.
# Exits 0 only if every check passes and both post-apply plans are clean.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5
IMG=chrislusf/seaweedfs:4.48
NET=spike-wi-5-net; S=spike-swfs-wi-5; I=spike-issuer-wi-5
export TF_PLUGIN_CACHE_DIR=$HOME/.terraform.d/plugin-cache TF_IN_AUTOMATION=1
W=$(mktemp -d "$HOME/.spike-wi-5-XXXX")
cleanup() { docker rm -f -v $S $I >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
cleanup; W=$(mktemp -d "$HOME/.spike-wi-5-XXXX")
cp $D/main.tf "$W/"; printf '[master.volume_growth]\ncopy_1 = 2\n' > "$W/master.toml"
docker network create $NET >/dev/null
docker run -d --name $I --network $NET --network-alias issuer -p 127.0.0.1::8080 -v $D/issuer.py:/issuer.py:ro \
  python:3.12-alpine sh -c 'pip install -q "pyjwt[crypto]" 2>/dev/null && python /issuer.py' >/dev/null
FLAGS=(-dir=/data -s3 -s3.port=8333 -s3.config=/s3.json -s3.iam.config=/iam.json -s3.iam.readOnly=false
       -ip=127.0.0.1 -ip.bind=127.0.0.1 -s3.ip.bind=0.0.0.0 -metricsIp=0.0.0.0 -metricsPort=9327
       -volume.max=0 -master.volumeSizeLimitMB=1024 -master.volumePreallocate=false
       -s3.port.iceberg=0 -s3.port.lance=0)
echo "weed server ${FLAGS[*]}"
docker create --name $S --network $NET -p 127.0.0.1::8333 $IMG server "${FLAGS[@]}" >/dev/null
docker cp $D/s3.json $S:/s3.json; docker cp $D/iam.json $S:/iam.json; docker cp "$W/master.toml" $S:/etc/seaweedfs/master.toml
docker start $S >/dev/null
IPORT=$(docker port $I 8080/tcp | head -1 | sed 's/.*://')
for _ in $(seq 90); do curl -sf -o /dev/null "http://127.0.0.1:$IPORT/.well-known/jwks.json" && break; sleep 2; done
wait_up() {
  PORT=$(docker port $S 8333/tcp | head -1 | sed 's/.*://')
  for _ in $(seq 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz")" = 200 ] && break; sleep 1; done
  sleep 3; echo "s3 on $PORT, issuer on $IPORT"
}
PY() { uv run -q --no-project --with boto3 python3 -I $D/probe.py "$@"; }
tf() { terraform -chdir="$W" "$@" -no-color -input=false -var endpoint=http://127.0.0.1:$PORT; }
wait_up
echo "== phase first"
R1=0; PY first $PORT $IPORT - - || R1=$?
terraform -chdir="$W" init -input=false -no-color >/dev/null || { echo "terraform init failed"; exit 3; }
tf apply -auto-approve > "$W/apply.log" 2>&1; A=$?
grep -E 'Error|error|Creation complete|Apply complete' "$W/apply.log" | head -20; echo "apply exit $A"
TFID=$(terraform -chdir="$W" output -raw id 2>/dev/null || echo -); TFSEC=$(terraform -chdir="$W" output -raw secret 2>/dev/null || echo -)
tf plan -detailed-exitcode > "$W/plan2.log" 2>&1; P2=$?
grep -vE '^\s*$|Refreshing|Reading|Read complete' "$W/plan2.log" | head -30; echo "second plan exit $P2 (0 clean)"
sleep 2
R2=0; PY first-tf $PORT $IPORT "$TFID" "$TFSEC" || R2=$?
echo "== docker restart"
docker restart $S >/dev/null; wait_up
R3=0; PY restart $PORT $IPORT "$TFID" "$TFSEC" || R3=$?
tf plan -detailed-exitcode > "$W/plan3.log" 2>&1; P3=$?
grep -vE '^\s*$|Refreshing|Reading|Read complete' "$W/plan3.log" | head -30; echo "post-restart plan exit $P3 (0 clean)"
echo "-- server log lines on iam/sts/policy"
docker logs $S 2>&1 | grep -iE 'iam|sts|defaultEffect|policy engine|identit' | sort | uniq -c | sort -rn | head -15
echo "SUMMARY admin_first=$R1 apply=$A plan2=$P2 checks_first=$R2 checks_restart=$R3 plan_restart=$P3"
[ $R1 = 0 ] && [ $A = 0 ] && [ $P2 = 0 ] && [ $R2 = 0 ] && [ $R3 = 0 ] && [ $P3 = 0 ]
