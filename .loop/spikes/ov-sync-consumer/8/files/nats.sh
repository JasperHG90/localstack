#!/usr/bin/env bash
# Runs the SeaweedFS 4.48 filer's gocdk_pub_sub notifier against NATS with
# JetStream and writes one line per captured message to nats-results.txt:
# its sequence number and the file path it names. Needs the `_full` image,
# the only build with the gocdk tag. Needs Docker. Leaves nothing running.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/nats-results.txt
P=okfnats
NET=$P-net
AWS_IMG=docker.io/amazon/aws-cli:2.27.0
BOX_IMG=docker.io/natsio/nats-box:0.17.0
W=$(mktemp -d)
chmod 755 "$W"

cleanup() {
  docker rm -f $P-nats $P-seaweed >/dev/null 2>&1 || true
  docker network rm $NET >/dev/null 2>&1 || true
  rm -rf "$W"
}
trap cleanup EXIT

cat >"$W/notification.toml" <<'EOF'
[notification.gocdk_pub_sub]
enabled = true
topic_url = "nats://seaweedfs.filer.events"
EOF
echo "# prototype" >"$W/a.md"

nats() { docker run --rm --network $NET $BOX_IMG nats -s nats://$P-nats:4222 "$@"; }
aws() {
  docker run --rm --network $NET -e AWS_ACCESS_KEY_ID=x -e AWS_SECRET_ACCESS_KEY=x \
    -e AWS_DEFAULT_REGION=us-east-1 -v "$W:/w:ro" $AWS_IMG \
    --endpoint-url http://$P-seaweed:8333 "$@" >/dev/null
}

docker network create $NET >/dev/null
docker run -d --name $P-nats --network $NET docker.io/library/nats:2.11-alpine -js >/dev/null
sleep 2
nats stream add SWFS --subjects seaweedfs.filer.events --storage file \
  --retention limits --discard old --max-age 1h --defaults >/dev/null
docker run -d --name $P-seaweed --network $NET -e NATS_SERVER_URL=nats://$P-nats:4222 \
  -v "$W/notification.toml:/etc/seaweedfs/notification.toml:ro" \
  docker.io/chrislusf/seaweedfs:4.48_full server -s3 -filer -ip=$P-seaweed >/dev/null
for _ in $(seq 1 60); do
  aws s3 ls 2>/dev/null && break
  sleep 2
done
aws s3 mb s3://ov-sync
aws s3 cp /w/a.md s3://ov-sync/JasperHG90/localstack/docs/a.md
aws s3 rm s3://ov-sync/JasperHG90/localstack/docs/a.md
sleep 3

count=$(nats stream info SWFS --json | grep -o '"messages": [0-9]*' | grep -o '[0-9]*$')
{
  echo "messages: $count"
  # Each body is a gocloud gob envelope around a protobuf EventNotification.
  # Its metadata holds "key", one length byte, then the file path.
  for seq in $(seq 1 "$count"); do
    nats stream get SWFS "$seq" >"$W/msg" 2>/dev/null
    path=$(python3 -c '
import sys
data = open(sys.argv[1], "rb").read()
at = data.find(b"\x03key") + 4
print(data[at + 1 : at + 1 + data[at]].decode())' "$W/msg")
    echo "#$seq $path"
  done
} >"$OUT"
cat "$OUT"
