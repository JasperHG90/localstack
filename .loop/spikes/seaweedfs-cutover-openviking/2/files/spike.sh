#!/usr/bin/env bash
# Spike: do OpenViking's directory markers survive the backup (rclone sync
# MinIO -> GCS, stood in for by a local dir) and the restore (rclone copy ->
# SeaweedFS 4.48)? Runs the backup job's exact command, then candidate flags.
# Exits 0 only if, with the chosen flags, OpenViking sees the same tree on
# SeaweedFS as on MinIO and VikingFS.mv works on the old paths.
set -uo pipefail
D=$(cd "$(dirname "$0")" && pwd)
NET=spike-ov2-net
OV=ghcr.io/jasperhg90/openviking:v0.4.17.1-9
AK=spikeaccesskey; SK=spikesecretkey123
W=$(mktemp -d); chmod 777 "$W"
cleanup() {
  docker rm -f -v spike-ov2-minio spike-ov2-swfs >/dev/null 2>&1
  docker volume rm spike-ov2-backup >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1; rm -rf "$W"
}
trap cleanup EXIT
cleanup; W=$(mktemp -d); chmod 777 "$W"
docker network create $NET >/dev/null; docker volume create spike-ov2-backup >/dev/null
docker run -d --name spike-ov2-minio --network $NET -p 127.0.0.1::9000 \
  -e MINIO_ROOT_USER=$AK -e MINIO_ROOT_PASSWORD=$SK pgsty/minio:latest server /data >/dev/null
docker run -d --name spike-ov2-swfs --network $NET -p 127.0.0.1::8333 --entrypoint sh chrislusf/seaweedfs:4.48 -c "
cat > /s3.json <<J
{\"identities\":[{\"name\":\"admin\",\"credentials\":[{\"accessKey\":\"$AK\",\"secretKey\":\"$SK\"}],\"actions\":[\"Admin\",\"Read\",\"Write\",\"List\",\"Tagging\"]}]}
J
mkdir -p /data && exec weed server -dir=/data -ip=spike-ov2-swfs -ip.bind=0.0.0.0 -volume.max=64 -master.volumeSizeLimitMB=64 -s3 -s3.port=8333 -s3.config=/s3.json" >/dev/null
MP=$(docker port spike-ov2-minio 9000/tcp | head -1 | sed 's/.*://')
SP=$(docker port spike-ov2-swfs 8333/tcp | head -1 | sed 's/.*://')
rc() {
  docker run --rm --network $NET -v spike-ov2-backup:/backup \
    -e RCLONE_CONFIG_MINIO_TYPE=s3 -e RCLONE_CONFIG_MINIO_PROVIDER=Minio \
    -e RCLONE_CONFIG_MINIO_ACCESS_KEY_ID=$AK -e RCLONE_CONFIG_MINIO_SECRET_ACCESS_KEY=$SK \
    -e RCLONE_CONFIG_MINIO_ENDPOINT=http://spike-ov2-minio:9000 \
    -e RCLONE_CONFIG_SWFS_TYPE=s3 -e RCLONE_CONFIG_SWFS_PROVIDER=SeaweedFS \
    -e RCLONE_CONFIG_SWFS_ACCESS_KEY_ID=$AK -e RCLONE_CONFIG_SWFS_SECRET_ACCESS_KEY=$SK \
    -e RCLONE_CONFIG_SWFS_ENDPOINT=http://spike-ov2-swfs:8333 \
    --entrypoint sh rclone/rclone:latest -c "$*"
}
ov() { docker run --rm --network $NET -v "$D/ov_tree.py:/p.py:ro" -v "$W:/w" \
  --entrypoint /app/.venv/bin/python $OV -I /p.py "$1" "$2" "$3" $AK $SK /w/base.json; }
keys() { uv run -q --no-project --with boto3 python3 -I "$D/keys.py" "$1" "$2" $AK $SK; }
for _ in $(seq 60); do rc "rclone lsd minio: && rclone lsd swfs:" >/dev/null 2>&1 && break; sleep 1; done
sleep 2
rc "rclone mkdir minio:openviking"
echo "== stage 0: OpenViking writes the tree onto MinIO"
ov build http://spike-ov2-minio:9000 openviking || { echo "BUILD FAILED"; exit 2; }
keys "http://127.0.0.1:$MP" openviking
fail=0
restore() { # name backup_flags restore_flags via(local|bucket)
  local n=$1 bf=$2 rf=$3 via=$4 src
  echo "== scenario $n: backup flags [${bf:-none}] restore flags [${rf:-none}] via $via"
  if [ "$via" = local ]; then
    src=/backup/$n
    rc "rclone sync $bf minio:openviking $src/" || echo "  backup sync exited $?"
    rc "echo \"  local copy: \$(find $src -type f | wc -l) files, \$(find $src -mindepth 1 -type d | wc -l) dirs, \$(find $src -type d -empty | wc -l) empty dirs\""
  else
    src=minio:standin-$n
    rc "rclone mkdir $src && rclone sync $bf minio:openviking $src/" || echo "  backup sync exited $?"
    keys "http://127.0.0.1:$MP" standin-$n | sed 's/^/  bucket stand-in /'
  fi
  rc "rclone mkdir swfs:ov-$n && rclone copy $rf $src swfs:ov-$n" || echo "  restore copy exited $?"
  keys "http://127.0.0.1:$SP" ov-$n | sed 's/^/  seaweedfs /'
  rc "rclone check --size-only minio:openviking swfs:ov-$n >/dev/null 2>&1; echo \"  rclone check exit \$?\""
  ov check http://spike-ov2-swfs:8333 ov-$n; return $?
}
restore a "" "" local; a=$?
restore b "--create-empty-src-dirs" "--create-empty-src-dirs --s3-directory-markers" local || fail=1
restore c "--create-empty-src-dirs --s3-directory-markers" "--create-empty-src-dirs --s3-directory-markers" bucket || fail=1
docker logs spike-ov2-swfs 2>&1 | grep -iE "failed to pick|InternalError" | head -3
echo "== summary: default flags (backup job today) exit $a, chosen flags $([ $fail = 0 ] && echo pass || echo FAIL)"
exit $fail
