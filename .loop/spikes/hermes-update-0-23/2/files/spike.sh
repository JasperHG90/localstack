#!/usr/bin/env bash
# Spike hermes-update-0-23 risk 1: on nousresearch/hermes-agent:v0.23.4 (arm64), does the
# repo's faster-whisper RUN line, with uv swapped to the base's uv-0.13.5, build; does the
# image import faster_whisper with av 18.1.0; and does the gateway voice path
# (drive.py, reused from spike:ov-save-skill/10) transcribe a short .ogg with model base?
set -u
D=/home/vscode/spike-scratch/hermes-1
BASE=nousresearch/hermes-agent:v0.23.4
TAG=h023-fw-$$
VOL=$TAG-data
IMG=$TAG:spike
W=$(mktemp -d "$D/run.XXXX"); chmod 755 "$W"
cleanup() { docker rm -f $TAG-tts $TAG-chk $TAG-a >/dev/null 2>&1; docker volume rm $VOL >/dev/null 2>&1; docker rmi $IMG >/dev/null 2>&1; }
trap cleanup EXIT
cp "$D/drive.py" "$W/drive.py"

echo "== make voice.ogg (espeak-ng -> ffmpeg libopus, as Telegram sends)"
docker run --rm --name $TAG-tts -v "$W:/w" debian:trixie-slim sh -c '
  apt-get update -qq >/dev/null && apt-get install -y -qq espeak-ng ffmpeg >/dev/null 2>&1 &&
  espeak-ng -s 140 -w /w/v.wav "The quick brown fox jumps over the lazy dog. Please save this link." &&
  ffmpeg -loglevel error -i /w/v.wav -ac 1 -ar 48000 -c:a libopus -b:a 32k /w/voice.ogg && chmod 644 /w/voice.ogg' || exit 10
ls -l "$W/voice.ogg"

echo "== build: FROM v0.23.4 + the repo's RUN line with uv-0.13.5, --no-cache"
mkdir "$W/build"
U=/opt/hermes/tools/uv-0.13.5-linux-arm64/uv
printf 'FROM %s\nUSER root\nRUN cd /opt/hermes && %s export --frozen --no-hashes --extra stt-whisper --no-emit-project -q -o /tmp/stt.txt && %s pip install --no-cache --python /opt/hermes/.venv/bin/python -c /tmp/stt.txt faster-whisper==1.2.1 && rm /tmp/stt.txt\n' $BASE $U $U > "$W/build/Dockerfile"
cat "$W/build/Dockerfile"
docker build --no-cache --platform linux/arm64 --progress plain -t $IMG "$W/build" 2>&1 | grep -vE '^#[0-9]+ (sha256|extracting|resolve|DONE 0)' | tail -40
[ "${PIPESTATUS[0]}" -eq 0 ] || exit 11

echo "== import as uid 10000, require av 18.1.0"
docker run --rm --name $TAG-chk --user 10000:10000 --entrypoint /opt/hermes/.venv/bin/python $IMG \
  -c 'import sys, faster_whisper, ctranslate2, av; print("python", sys.version.split()[0], "faster_whisper", faster_whisper.__version__, "ctranslate2", ctranslate2.__version__, "av", av.__version__); sys.exit(0 if av.__version__ == "18.1.0" else 4)' || exit 12
docker image inspect -f '{{.Size}}' $BASE $IMG | awk 'NR==1{a=$1} NR==2{printf "image grew by %d MB\n", ($1-a)/2^20}'

docker volume create $VOL >/dev/null
CFG='model:\n  provider: bifrost\n'
echo "== gateway voice path, default STT config, fresh /opt/data, 2048 MB cap"
docker run --name $TAG-a --memory 2048m --memory-swap 2048m --user 10000:10000 \
  -e HOME=/opt/data -e CFG="$CFG" -v $VOL:/opt/data -v "$W:/w:ro" --entrypoint sh $IMG -c '
  printf "$CFG" > /opt/data/config.yaml
  { /opt/hermes/.venv/bin/python /w/drive.py /w/voice.ogg; echo $? > /tmp/rc; } 2>&1 | grep -v "hermes_cli.plugins INFO"
  rc=$(cat /tmp/rc)
  echo "drive exit $rc"
  du -sh /opt/data/.cache/huggingface/hub/* 2>/dev/null
  exit $rc'
A=$?
echo "container exit $A, OOMKilled=$(docker inspect -f '{{.State.OOMKilled}}' $TAG-a)"
exit $A
