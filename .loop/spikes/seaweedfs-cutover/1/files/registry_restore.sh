#!/usr/bin/env bash
# Spike: does a registry bucket restored MinIO -> rclone -> (local dir standing
# in for GCS) -> SeaweedFS still serve every image, by tag and by digest?
# Exits 0 only when both restore paths serve every image intact.
# Needs the docker volume spike-cut-minio-bin holding a minio binary built from
# RELEASE.2025-09-07T16-13-09Z (the tag in minio.hcl; the image is no longer
# published on Docker Hub or quay).
set -uo pipefail

NET=spike-cut-net
REGISTRY_IMG=docker.io/library/registry:3.1.1
SWFS_IMG=docker.io/chrislusf/seaweedfs:4.48
RCLONE_IMG=docker.io/rclone/rclone:latest
CRANE_IMG=gcr.io/go-containerregistry/crane:debug
AK=spikeaccesskey
SK=spikesecretkey123

cleanup() {
  docker rm -f spike-cut-minio spike-cut-swfs spike-cut-reg-a spike-cut-reg-b spike-cut-reg-c >/dev/null 2>&1
  docker volume rm spike-cut-backup spike-cut-work >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1
}
trap cleanup EXIT
cleanup
docker network create $NET >/dev/null
docker volume create spike-cut-backup >/dev/null
docker volume create spike-cut-work >/dev/null

docker run -d --name spike-cut-minio --network $NET \
  -v spike-cut-minio-bin:/bin-minio:ro \
  -e MINIO_ROOT_USER=$AK -e MINIO_ROOT_PASSWORD=$SK \
  docker.io/library/alpine:3 /bin-minio/minio server /data >/dev/null

docker run -d --name spike-cut-swfs --network $NET --entrypoint sh $SWFS_IMG -c "
cat > /s3.json <<EOF
{\"identities\":[{\"name\":\"admin\",\"credentials\":[{\"accessKey\":\"$AK\",\"secretKey\":\"$SK\"}],\"actions\":[\"Admin\",\"Read\",\"Write\",\"List\",\"Tagging\"]}]}
EOF
mkdir -p /data && exec weed server -dir=/data -ip=spike-cut-swfs -ip.bind=0.0.0.0 -s3 -s3.port=8333 -s3.config=/s3.json" >/dev/null

rc() {
  docker run --rm --network $NET -v spike-cut-backup:/backup \
    -e RCLONE_CONFIG_MINIO_TYPE=s3 -e RCLONE_CONFIG_MINIO_PROVIDER=Minio \
    -e RCLONE_CONFIG_MINIO_ACCESS_KEY_ID=$AK -e RCLONE_CONFIG_MINIO_SECRET_ACCESS_KEY=$SK \
    -e RCLONE_CONFIG_MINIO_ENDPOINT=http://spike-cut-minio:9000 \
    -e RCLONE_CONFIG_SWFS_TYPE=s3 -e RCLONE_CONFIG_SWFS_PROVIDER=SeaweedFS \
    -e RCLONE_CONFIG_SWFS_ACCESS_KEY_ID=$AK -e RCLONE_CONFIG_SWFS_SECRET_ACCESS_KEY=$SK \
    -e RCLONE_CONFIG_SWFS_ENDPOINT=http://spike-cut-swfs:8333 \
    $RCLONE_IMG "$@"
}

registry() { # name endpoint bucket
  docker run -d --name "$1" --network $NET --entrypoint sh $REGISTRY_IMG -c "
cat > /tmp/config.yml <<EOF
version: 0.1
log:
  level: warn
storage:
  s3:
    regionendpoint: $2
    forcepathstyle: true
    secure: false
    region: us-east-1
    bucket: $3
    accesskey: $AK
    secretkey: $SK
  delete:
    enabled: true
http:
  addr: 0.0.0.0:5000
  relativeurls: true
EOF
exec registry serve /tmp/config.yml" >/dev/null
}

crane() {
  docker run --rm --network $NET -v spike-cut-work:/work -w /work --entrypoint sh $CRANE_IMG -c "$1"
}

wait_for() { # description command...
  for _ in $(seq 1 60); do "${@:2}" >/dev/null 2>&1 && return 0; sleep 1; done
  echo "TIMEOUT waiting for $1"; exit 2
}

wait_for minio rc lsd minio:
rc mkdir minio:registry
registry spike-cut-reg-a http://spike-cut-minio:9000 registry
wait_for reg-a crane "wget -q -O- http://spike-cut-reg-a:5000/v2/"

echo "== push to registry on MinIO"
crane '
set -e
mk() { mkdir -p d$1 && head -c $2 /dev/urandom > d$1/f$1 && tar czf l$1.tgz -C d$1 . ; }
mk 1 1048576; mk 2 2097152; mk 3 524288; mk 4 31457280
R=spike-cut-reg-a:5000
crane append --insecure -f l1.tgz -t $R/small:v1
crane append --insecure -b $R/small:v1 -f l2.tgz -t $R/small:v1
crane append --insecure -b $R/small:v1 -f l3.tgz -t $R/small:v1
crane append --insecure -f l4.tgz -t $R/big:v1
crane digest --insecure $R/small:v1 > small.digest
crane digest --insecure $R/big:v1 > big.digest
echo "small $(cat small.digest)  big $(cat big.digest)"
crane manifest --insecure $R/small:v1 | grep -c "\"digest\"" | sed "s/^/small manifest digests: /"
crane manifest --insecure $R/big:v1
ls -l l4.tgz | awk "{print \"big layer bytes:\", \$5}"
' || { echo "PUSH FAILED"; exit 2; }

echo "== MinIO objects (data blobs, md5 empty means multipart ETag)"
rc lsjson -R --hash --files-only minio:registry \
  | grep '/data"' | sed -E 's/.*"Path":"([^"]*)".*"Size":([0-9]+).*"Hashes":\{([^}]*)\}.*/\2 \3 \1/'

echo "== rclone sync MinIO -> local dir (GCS stand-in)"
rc sync minio:registry /backup/minio/registry/ || { echo "SYNC TO BACKUP FAILED"; exit 2; }
echo "== rclone copy local dir -> SeaweedFS registry"
rc mkdir swfs:registry
rc copy /backup/minio/registry/ swfs:registry || { echo "RESTORE FAILED"; exit 2; }
echo "== rclone sync MinIO -> SeaweedFS registry-direct (S3 to S3)"
rc mkdir swfs:registry-direct
rc sync minio:registry swfs:registry-direct || { echo "DIRECT COPY FAILED"; exit 2; }

for b in minio:registry /backup/minio/registry swfs:registry swfs:registry-direct; do
  printf '%-24s ' "$b"; rc size "$b" | tr '\n' ' '; echo
done
echo "== rclone check MinIO vs SeaweedFS (size only, ETags differ)"
rc check --size-only minio:registry swfs:registry 2>&1 | tail -2
rc check --size-only minio:registry swfs:registry-direct 2>&1 | tail -2

docker rm -f spike-cut-reg-a >/dev/null
registry spike-cut-reg-b http://spike-cut-swfs:8333 registry
registry spike-cut-reg-c http://spike-cut-swfs:8333 registry-direct
wait_for reg-b crane "wget -q -O- http://spike-cut-reg-b:5000/v2/"
wait_for reg-c crane "wget -q -O- http://spike-cut-reg-c:5000/v2/"

fail=0
for r in spike-cut-reg-b spike-cut-reg-c; do
  echo "== pull from $r"
  crane "
set -e
R=$r:5000
crane catalog --insecure \$R | tr '\n' ' '; echo
for i in small big; do
  d=\$(crane digest --insecure \$R/\$i:v1)
  [ \"\$d\" = \"\$(cat \$i.digest)\" ] || { echo \"\$i: tag digest \$d != pushed \$(cat \$i.digest)\"; exit 1; }
  crane validate --insecure --remote \$R/\$i:v1
  crane validate --insecure --remote \$R/\$i@\$d
  crane pull --insecure \$R/\$i@\$d /tmp/\$i.tar && echo \"\$i pulled by digest \$d (\$(wc -c < /tmp/\$i.tar) bytes tar)\"
  for l in \$(crane manifest --insecure \$R/\$i@\$d | grep -o 'sha256:[0-9a-f]*' | sort -u); do
    got=sha256:\$(crane blob --insecure \$R/\$i@\$l | sha256sum | cut -d' ' -f1)
    [ \"\$got\" = \"\$l\" ] || { echo \"\$i blob \$l served \$got\"; exit 1; }
  done
  echo \"\$i: every blob's sha256 matches its digest\"
done
" || { echo "FAIL on $r"; fail=1; }
  docker logs "$r" 2>&1 | grep -i 'error' | head -5
done

[ $fail -eq 0 ] && echo "RESULT: both restore paths serve every image intact" || echo "RESULT: restore broke the registry"
exit $fail
