#!/usr/bin/env bash
# Apply today's openviking catalog, then the plan's move of the openviking
# user's policy to openviking-v2, on a local SeaweedFS 4.48 with the service's
# flags. Exit 0 only if the second apply succeeds, the key is unchanged, the
# third plan is clean, and the key is denied on openviking but full on -v2.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy
IMG=chrislusf/seaweedfs:4.48; S=spike-swfs-ovpolicy
W=$(mktemp -d "$D/run-XXXX")
export TF_DATA_DIR=$W/.terraform TF_IN_AUTOMATION=1 TF_CLI_CONFIG_FILE=$W/tf.rc UV_CACHE_DIR=$D/uv-cache
cat > "$W/tf.rc" <<RC
provider_installation {
  filesystem_mirror {
    path    = "/home/vscode/.terraform.d/plugin-cache"
    include = ["registry.terraform.io/hashicorp/aws"]
  }
}
RC
cleanup() { docker rm -f -v $S >/dev/null 2>&1; }
trap cleanup EXIT
cleanup
cp $D/main.tf "$W/"; printf '[master.volume_growth]\ncopy_1 = 2\n' > "$W/master.toml"
FLAGS=(-dir=/data -s3 -s3.port=8333 -s3.config=/s3.json -s3.iam.config=/iam.json -s3.iam.readOnly=false
       -s3.port.iceberg=0 -s3.port.lance=0 -ip=127.0.0.1 -ip.bind=127.0.0.1 -s3.ip.bind=0.0.0.0
       -metricsIp=0.0.0.0 -metricsPort=9327 -volume.max=0 -master.volumeSizeLimitMB=1024
       -master.volumePreallocate=false)
docker create --name $S -p 127.0.0.1::8333 $IMG server "${FLAGS[@]}" >/dev/null
docker cp $D/s3.json $S:/s3.json; docker cp $D/iam.json $S:/iam.json; docker cp "$W/master.toml" $S:/etc/seaweedfs/master.toml
docker start $S >/dev/null
PORT=$(docker port $S 8333/tcp | head -1 | sed 's/.*://')
for _ in $(seq 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz")" = 200 ] && break; sleep 1; done
sleep 3; echo "s3 on $PORT"
tf() { terraform -chdir="$W" "$@" -no-color -input=false -var endpoint=http://127.0.0.1:$PORT; }
out() { terraform -chdir="$W" output -raw "$1" 2>/dev/null || echo -; }
PY() { uv run -q --no-project --with boto3 python3 -I $D/probe.py "$@"; }
terraform -chdir="$W" init -input=false -no-color >/dev/null || { echo "terraform init failed"; exit 3; }

echo "== step 1: openviking user on bucket openviking"
tf apply -auto-approve -var step=1 > "$W/a1.log" 2>&1; A1=$?
grep -E 'Error|Apply complete' "$W/a1.log"; echo "apply1 exit $A1"
ID1=$(out ov_id); SEC1=$(out ov_secret); BK=$(out backup_id); BKS=$(out backup_secret)
echo "ov key after step 1: $ID1 (secret sha $(printf %s "$SEC1" | sha256sum | cut -c1-12))"
sleep 2; R1=0; PY step1 $PORT "$ID1" "$SEC1" "$BK" "$BKS" || R1=$?

echo "== step 2: policy moved to openviking-v2"
tf plan -var step=2 > "$W/p2.log" 2>&1
grep -E '^\s+# |Plan:' "$W/p2.log"
tf apply -auto-approve -var step=2 > "$W/a2.log" 2>&1; A2=$?
grep -E 'Error|error|Destroy|Creation|Modif|Apply complete' "$W/a2.log" | head -30; echo "apply2 exit $A2"
ID2=$(out ov_id); SEC2=$(out ov_secret)
echo "ov key after step 2: $ID2 (secret sha $(printf %s "$SEC2" | sha256sum | cut -c1-12))"
SAME=1; [ "$ID1" = "$ID2" ] && [ "$SEC1" = "$SEC2" ] && [ "$ID1" != - ] && SAME=0; echo "key unchanged: $([ $SAME = 0 ] && echo yes || echo no)"

tf plan -detailed-exitcode -var step=2 > "$W/p3.log" 2>&1; P3=$?
grep -vE '^\s*$|Refreshing|Reading|Read complete' "$W/p3.log" | head -30; echo "third plan exit $P3 (0 clean)"
echo "-- policies on user openviking (admin view)"
AWS_ACCESS_KEY_ID=SPIKEADMINKEY0000001 AWS_SECRET_ACCESS_KEY=spikeAdminSecret0000000000000000000000001 \
  uv run -q --no-project --with boto3 python3 -I -c "
import boto3,sys
c=boto3.client('iam',endpoint_url='http://127.0.0.1:$PORT',region_name='us-east-1')
print('policies', c.list_user_policies(UserName='openviking')['PolicyNames'])
print('keys', [k['AccessKeyId'] for k in c.list_access_keys(UserName='openviking')['AccessKeyMetadata']])
" || echo "iam list failed"
sleep 2; R2=0; PY step2 $PORT "$ID2" "$SEC2" "$BK" "$BKS" || R2=$?

echo "== docker restart"
docker restart $S >/dev/null
PORT=$(docker port $S 8333/tcp | head -1 | sed 's/.*://')
for _ in $(seq 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz")" = 200 ] && break; sleep 1; done
sleep 3
R3=0; PY step2 $PORT "$ID2" "$SEC2" "$BK" "$BKS" || R3=$?
echo "SUMMARY apply1=$A1 checks1=$R1 apply2=$A2 key_same=$SAME plan3=$P3 checks2=$R2 checks_restart=$R3"
[ $A1 = 0 ] && [ $R1 = 0 ] && [ $A2 = 0 ] && [ $SAME = 0 ] && [ $P3 = 0 ] && [ $R2 = 0 ] && [ $R3 = 0 ]
