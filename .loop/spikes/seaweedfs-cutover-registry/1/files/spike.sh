#!/usr/bin/env bash
# Spike: with only RegistryRole creds from the registry.hcl credential_process
# helper (plus &RoleArn=&RoleSessionName=), does registry 3.1.1 on SeaweedFS
# 4.48 (production weed server flags, copy_1 = 2) push a >=100 MiB layer
# (multipart + UploadPartCopy) and a small one (CopyObject), serve both by
# digest, garbage-collect a deleted image, and take a push again?
# Phase "full" grants s3:* on the bucket, phase "min" grants $MIN only. Both
# gate the exit. With ABLATE=1, also reruns "min" minus each action (report only).
# Extends spike seaweedfs-cutover/3 and seaweedfs-workload-identity/4. Run from repo root.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2
P=spike-reg2
NET=$P-net; S=$P-swfs; I=$P-issuer; REG=$P-reg; WORK=$P-work
SWFS_IMG=chrislusf/seaweedfs:4.48
REGISTRY_IMG=docker.io/library/registry:3.1.1
CRANE_IMG=gcr.io/go-containerregistry/crane:debug
RCLONE_IMG=docker.io/rclone/rclone:latest
AK=SPIKEADMINKEY0000001; SK=spikeAdminSecret0000000000000000000000001
MIN=${MIN:-s3:GetObject s3:PutObject s3:DeleteObject s3:ListBucket s3:ListBucketMultipartUploads s3:AbortMultipartUpload s3:ListMultipartUploadParts}
ABLATE=${ABLATE:-1}

W=$(mktemp -d -p "$D")
cleanup() {
  docker rm -f -v $REG $S $I >/dev/null 2>&1
  docker volume rm $WORK >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1
}
trap 'cleanup; rm -rf "$W"' EXIT
cleanup
docker network create $NET >/dev/null
docker volume create $WORK >/dev/null
docker run -d --name $I --network $NET --network-alias issuer -v $D/issuer.py:/issuer.py:ro \
  python:3.12-alpine sh -c 'pip install -q "pyjwt[crypto]" 2>/dev/null && python /issuer.py' >/dev/null
printf '[master.volume_growth]\ncopy_1 = 2\n' > $W/master.toml

# registry.hcl's helper as rendered, pointed at SeaweedFS, plus RoleArn/RoleSessionName.
awk '/#!\/bin\/sh/{p=1} p&&/^        EOF/{exit} p' deployments/applications/services/registry.hcl \
  | sed -e 's/^        //' -e 's/\$\$/$/g' -e "s|\${minio_host}:9000|$S:8333|" \
        -e 's|WebIdentityToken=\${jwt}"|WebIdentityToken=${jwt}\&RoleArn=arn:aws:iam::role/RegistryRole\&RoleSessionName=registry"|' \
  > $W/minio-creds.sh
grep -q 'RoleSessionName=registry"' $W/minio-creds.sh || { echo "helper template changed"; exit 3; }
chmod 755 $W/minio-creds.sh
printf '[default]\ncredential_process = /local/minio-creds.sh\n' > $W/aws-config
# config.yml as registry.hcl renders it, minus htpasswd/debug, endpoint on SeaweedFS. No keys.
cat > $W/config.yml <<EOF
version: 0.1
log:
  level: info
storage:
  s3:
    regionendpoint: http://$S:8333
    forcepathstyle: true
    secure: false
    region: us-east-1
    bucket: registry
  delete:
    enabled: true
http:
  addr: 0.0.0.0:5000
  relativeurls: true
EOF

bb() { docker run --rm --network $NET busybox:1.37 "$@"; }
crane() { docker run --rm --network $NET -v $WORK:/work -w /work --entrypoint sh $CRANE_IMG -c "$1"; }
rc() {
  docker run --rm --network $NET -e RCLONE_CONFIG_SWFS_TYPE=s3 -e RCLONE_CONFIG_SWFS_PROVIDER=SeaweedFS \
    -e RCLONE_CONFIG_SWFS_ACCESS_KEY_ID=$AK -e RCLONE_CONFIG_SWFS_SECRET_ACCESS_KEY=$SK \
    -e RCLONE_CONFIG_SWFS_ENDPOINT=http://$S:8333 $RCLONE_IMG "$@"
}
etag() { # key: ETag as the admin sees it
  docker run --rm --network $NET curlimages/curl:8.11.1 -sI --aws-sigv4 aws:amz:us-east-1:s3 --user "$AK:$SK" \
    "http://$S:8333/registry/$1" | tr -d '\r' | awk -F': ' 'tolower($1)=="etag"{print $2} /^HTTP/{c=$2} END{if(c!=200)print "HTTP " c}'
}
for _ in $(seq 90); do bb wget -q -O /dev/null http://issuer:8080/.well-known/jwks.json 2>/dev/null && break; sleep 2; done

echo "== make layers in volume $WORK: 110 MiB and 1 MiB random"
crane 'set -e
mk() { mkdir -p d$1 && head -c $2 /dev/urandom > d$1/f$1 && tar cf l$1.tar -C d$1 . && rm -rf d$1; }
mk big 115343360; mk small 1048576; mk big2 1048576; ls -l *.tar' || exit 3

FLAGS=(-dir=/data -s3 -s3.port=8333 -s3.config=/s3.json -s3.iam.config=/iam.json -s3.iam.readOnly=false
       -ip=127.0.0.1 -ip.bind=127.0.0.1 -s3.ip.bind=0.0.0.0 -metricsIp=0.0.0.0 -metricsPort=9327
       -volume.max=0 -master.volumeSizeLimitMB=1024 -master.volumePreallocate=false
       -s3.port.iceberg=0 -s3.port.lance=0)
echo "weed server ${FLAGS[*]}"; echo "master.toml: copy_1 = 2"

run_phase() { # label actions...
  local label=$1; shift
  echo; echo "===== phase $label: Action = $*"
  docker rm -f -v $REG $S >/dev/null 2>&1
  jq --argjson a "$(printf '%s\n' "$@" | jq -R . | jq -s .)" '.policies[0].document.Statement[0].Action = $a' \
    $D/iam.tmpl.json > $W/iam.json
  docker create --name $S --network $NET $SWFS_IMG server "${FLAGS[@]}" >/dev/null
  docker cp $D/s3.json $S:/s3.json >/dev/null; docker cp $W/iam.json $S:/iam.json >/dev/null
  docker cp $W/master.toml $S:/etc/seaweedfs/master.toml >/dev/null
  docker start $S >/dev/null
  for _ in $(seq 60); do bb wget -q -O /dev/null http://$S:8333/healthz 2>/dev/null && break; sleep 1; done
  for _ in $(seq 30); do
    docker exec $S sh -c 'echo "s3.bucket.create -name registry" | weed shell' >/dev/null 2>&1
    docker exec $S sh -c 'echo s3.bucket.list | weed shell 2>&1' | grep -q registry && break; sleep 2
  done
  bb wget -q -O - "http://issuer:8080/mint?job=registry" > $W/registry.jwt
  docker run -d --name $REG --network $NET \
    -e AWS_SDK_LOAD_CONFIG=1 -e AWS_CONFIG_FILE=/local/aws-config -e AWS_REGION=us-east-1 \
    -v $W/minio-creds.sh:/local/minio-creds.sh:ro -v $W/aws-config:/local/aws-config:ro \
    -v $W/registry.jwt:/secrets/nomad_minio.jwt:ro -v $W/config.yml:/etc/cfg/config.yml:ro \
    $REGISTRY_IMG /etc/cfg/config.yml >/dev/null
  for _ in $(seq 30); do bb wget -q -O /dev/null http://$REG:5000/v2/ 2>/dev/null && break; sleep 1; done
  echo "helper as the registry runs it: $(docker exec $REG sh /local/minio-creds.sh 2>&1 | sed -E 's/"(SecretAccessKey|SessionToken)":"[^"]*"/"\1":"..."/g' | head -c 200)"

  local ok=1
  step() { echo "-- $1"; }
  step "push big (110 MiB layer) and small (1 MiB layer)"
  crane "set -e; R=$REG:5000
crane append --insecure -f lbig.tar -t \$R/big:v1 >/dev/null
crane append --insecure -f lsmall.tar -t \$R/small:v1 >/dev/null
crane digest --insecure \$R/big:v1 > big.digest; crane digest --insecure \$R/small:v1 > small.digest
crane manifest --insecure \$R/big:v1 | grep -o 'sha256:[0-9a-f]*' | tail -1 > big.layer
crane manifest --insecure \$R/small:v1 | grep -o 'sha256:[0-9a-f]*' | tail -1 > small.layer
echo big \$(cat big.digest) layer \$(cat big.layer) size \$(crane manifest --insecure \$R/big:v1 | grep -o '\"size\":[0-9]*' | tail -1)
echo small \$(cat small.digest) layer \$(cat small.layer)" || { echo "FAIL push"; ok=0; }
  local BL; BL=$(crane 'cut -d: -f2 big.layer' 2>/dev/null)
  if [ $ok = 1 ]; then
    local SL0; SL0=$(crane 'cut -d: -f2 small.layer' 2>/dev/null)
    for x in big:$BL small:$SL0; do # multipart ETag (-N) means UploadPartCopy, plain md5 means CopyObject
      local h=${x#*:}; echo "${x%%:*} blob ETag: $(etag "docker/registry/v2/blobs/sha256/${h:0:2}/$h/data")"
    done
  fi

  if [ $ok = 1 ]; then step "pull both by digest, validate, check every blob sha256"
    crane "set -e; R=$REG:5000
for i in big small; do
  d=\$(cat \$i.digest); crane validate --insecure --remote \$R/\$i@\$d
  for l in \$(crane manifest --insecure \$R/\$i@\$d | grep -o 'sha256:[0-9a-f]*' | sort -u); do
    got=sha256:\$(crane blob --insecure \$R/\$i@\$l | sha256sum | cut -d' ' -f1)
    [ \"\$got\" = \"\$l\" ] || { echo \"\$i blob \$l served \$got\"; exit 1; }
  done; echo \"\$i: blobs match\"
done" || { echo "FAIL pull"; ok=0; }
  fi

  if [ $ok = 1 ]; then step "delete big by digest (drops tag v1), garbage-collect with the same creds"
    crane "crane delete --insecure $REG:5000/big@\$(cat big.digest) && crane ls --insecure $REG:5000/big; echo tags-left=\$(crane ls --insecure $REG:5000/big | wc -l)" \
      || { echo "FAIL delete"; ok=0; }
    if [ $ok = 1 ]; then
      docker exec $REG registry garbage-collect /etc/cfg/config.yml > $W/gc.log 2>&1; local g=$?
      echo "gc exit $g; $(grep -c 'blob eligible for deletion' $W/gc.log) eligible, $(grep -ci 'deleting blob' $W/gc.log) deleting lines"
      grep -iE 'error|denied|fail' $W/gc.log | head -5
      [ $g = 0 ] || { echo "FAIL gc"; ok=0; }
      local left; left=$(rc lsf -R "swfs:registry/docker/registry/v2/blobs/sha256/${BL:0:2}/$BL/" 2>/dev/null | wc -l)
      local SL; SL=$(crane 'cut -d: -f2 small.layer')
      local sleft; sleft=$(rc lsf -R "swfs:registry/docker/registry/v2/blobs/sha256/${SL:0:2}/$SL/" 2>/dev/null | wc -l)
      echo "after gc: big layer objects left=$left, small layer objects left=$sleft"
      [ "$left" = 0 ] && [ "$sleft" -gt 0 ] || { echo "FAIL gc did not remove exactly the deleted blobs"; ok=0; }
      crane "crane blob --insecure $REG:5000/big@\$(cat big.layer) >/dev/null 2>&1 && echo 'big layer still served' || echo 'big layer no longer served'"
    fi
  fi

  if [ $ok = 1 ]; then step "push again after gc (big layer re-upload plus a new image), then pull and validate"
    crane "set -e; R=$REG:5000
crane append --insecure -f lbig.tar -t \$R/big:v2 >/dev/null
crane append --insecure -b \$R/small:v1 -f lbig2.tar -t \$R/small:v2 >/dev/null
for t in big:v2 small:v2 small:v1; do crane validate --insecure --remote \$R/\$t; done
echo re-push ok: \$(crane catalog --insecure \$R | tr '\n' ' ')" || { echo "FAIL re-push"; ok=0; }
  fi
  echo "-- registry log errors"; docker logs $REG 2>&1 | grep -iE 'level=error|accessdenied|denied' | sed -E 's/.*(err(or)?=)/\1/' | cut -c1-250 | sort | uniq -c | head -6
  docker run --rm --network $NET -v $WORK:/work busybox:1.37 sh -c 'rm -f /work/*.digest /work/*.layer'
  echo "RESULT phase $label ok=$ok"
  [ $ok = 1 ]
}

run_phase full 's3:*'; F=$?
run_phase min $MIN; M=$?
if [ "$ABLATE" = 1 ] && [ $M = 0 ]; then
  echo; echo "===== ablation: min minus one action each (report only)"
  for a in $MIN; do
    run_phase "min-minus-$a" $(printf '%s\n' $MIN | grep -vx "$a") > $W/abl.log 2>&1; r=$?
    echo "without $a: $([ $r = 0 ] && echo 'still passes (not needed)' || echo "fails at: $(grep -m1 '^FAIL' $W/abl.log)")"
  done
fi
echo; echo "SUMMARY full(s3:*)=$F min=$M  MIN: $MIN"
[ $F = 0 ] && [ $M = 0 ]
