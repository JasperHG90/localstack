#!/usr/bin/env bash
# Spike: with faster-whisper 1.2.1 baked into hermes 0.22.2-2 and the deployed config (no stt
# section), does the gateway voice path transcribe under 2048 MB, does the model land on
# /opt/data, and does a fresh container with --network none transcribe from that cache?
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2
BASE=ghcr.io/jasperhg90/hermes:0.22.2-2
TAG=ovsave-fw2-$$
VOL=$TAG-data
IMG=$TAG:spike
W=$(mktemp -d "$D/run.XXXX"); chmod 755 "$W"
cleanup() { docker rm -f $TAG-tts $TAG-chk $TAG-a $TAG-b >/dev/null 2>&1; docker volume rm $VOL >/dev/null 2>&1; docker rmi $IMG >/dev/null 2>&1; }
trap cleanup EXIT
cp "$D/drive.py" "$W/drive.py"

echo "== make voice.ogg (espeak-ng -> ffmpeg libopus, as Telegram sends)"
docker run --rm --name $TAG-tts -v "$W:/w" debian:trixie-slim sh -c '
  apt-get update -qq >/dev/null && apt-get install -y -qq espeak-ng ffmpeg >/dev/null 2>&1 &&
  espeak-ng -s 140 -w /w/v.wav "The quick brown fox jumps over the lazy dog. Please save this link." &&
  ffmpeg -loglevel error -i /w/v.wav -ac 1 -ar 48000 -c:a libopus -b:a 32k /w/voice.ogg && chmod 644 /w/voice.ogg' || exit 10
ls -l "$W/voice.ogg"

echo "== build with --no-cache"
mkdir "$W/build"
printf 'FROM %s\nUSER root\nRUN /opt/hermes/tools/uv-0.12.3-linux-arm64/uv pip install --no-cache --python /opt/hermes/.venv/bin/python faster-whisper==1.2.1\n' $BASE > "$W/build/Dockerfile"
cat "$W/build/Dockerfile"
docker build --no-cache -q -t $IMG "$W/build" || exit 11
echo "-- cache-proof check: import as uid 10000 in the new image"
docker run --rm --name $TAG-chk --user 10000:10000 --entrypoint /opt/hermes/.venv/bin/python $IMG \
  -c 'import faster_whisper, ctranslate2; print("faster_whisper", faster_whisper.__version__, "ctranslate2", ctranslate2.__version__)' || exit 12
docker image ls --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep -E "^($BASE|$IMG) "
docker image inspect -f '{{.Size}}' $BASE $IMG | awk 'NR==1{a=$1} NR==2{printf "image grew by %d MB\n", ($1-a)/2^20}'

docker volume create $VOL >/dev/null
# Deployed config: no stt section (only the model block matters here).
CFG='model:\n  provider: bifrost\n'
run() { # $1 suffix, $2 extra docker args
  docker run --name $TAG-$1 $2 --memory 2048m --memory-swap 2048m --user 10000:10000 \
    -e HOME=/opt/data -e CFG="$CFG" -v $VOL:/opt/data -v "$W:/w:ro" --entrypoint sh $IMG -c '
    printf "$CFG" > /opt/data/config.yaml
    /opt/hermes/.venv/bin/python /w/drive.py /w/voice.ogg; rc=$?
    echo "drive exit $rc"
    echo "-- model cache on /opt/data:"; du -sh /opt/data/.cache/huggingface/hub/* 2>/dev/null
    du -sh /opt/data 2>/dev/null
    exit $rc'
  rc=$?
  echo "container $1 exit $rc, OOMKilled=$(docker inspect -f '{{.State.OOMKilled}}' $TAG-$1)"
  return $rc
}
echo "== run A: first voice message, fresh /opt/data, network on"
run a ""; A=$?
echo "== run B: new container on the same /opt/data, --network none"
run b "--network none"; B=$?
echo "A=$A B=$B"
[ $A -eq 0 ] && [ $B -eq 0 ]
