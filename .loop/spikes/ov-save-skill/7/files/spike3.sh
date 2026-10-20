#!/usr/bin/env bash
# Spike: with faster-whisper 1.2.1 baked into the image venv and the deployed config (no stt section), does hermes 0.22.2-1 transcribe a Telegram .ogg under 2048 MB, and is the model download kept across a restart on /opt/data?
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice
BASE=ghcr.io/jasperhg90/hermes:0.22.2-1
TAG=ovsave-voice-$$
VOL=$TAG-data
W=$(mktemp -d "$D/run.XXXX"); chmod 755 "$W"
IMG=$TAG:spike
cleanup() { docker rm -f $TAG-tts $TAG-a $TAG-b >/dev/null 2>&1; docker volume rm $VOL >/dev/null 2>&1; docker rmi $IMG >/dev/null 2>&1; }
trap cleanup EXIT
cp "$D/drive.py" "$W/drive.py"; CFG="model:\n  provider: bifrost\n"

echo "== make voice.ogg (espeak-ng -> ffmpeg libopus, as Telegram sends)"
docker run --rm --name $TAG-tts -v "$W:/w" debian:trixie-slim sh -c '
  apt-get update -qq >/dev/null && apt-get install -y -qq espeak-ng ffmpeg >/dev/null 2>&1 &&
  espeak-ng -s 140 -w /w/v.wav "The quick brown fox jumps over the lazy dog. Please save this link." &&
  ffmpeg -loglevel error -i /w/v.wav -ac 1 -ar 48000 -c:a libopus -b:a 32k /w/voice.ogg && chmod 644 /w/voice.ogg' || exit 10
ls -l "$W/voice.ogg"

echo "== bake faster-whisper into the image venv"
mkdir "$W/build"
printf 'FROM %s\nUSER root\nRUN /opt/hermes/tools/uv-0.12.3-linux-arm64/uv pip install --no-cache --python /opt/hermes/.venv/bin/python faster-whisper==1.2.1\n' $BASE > "$W/build/Dockerfile"
cat "$W/build/Dockerfile"
docker build --progress=plain -t $IMG "$W/build" 2>&1 | grep -E 'Installed|Uninstalled| [-+~] [A-Za-z]' || exit 11
docker image ls --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep -E "^($BASE|$IMG) "
# /opt/data is a named volume, like the job's hermes_data_volume; seed it as the image does.
docker volume create $VOL >/dev/null
run() { # $1 = container name suffix
  docker run --name $TAG-$1 -e CFG="$2" --memory 2048m --memory-swap 2048m --user 10000:10000 \
    -e HERMES_HOME=/opt/data -v $VOL:/opt/data -v "$W:/w:ro" --entrypoint sh $IMG -c '
    printf "$CFG" > /opt/data/config.yaml; cat /opt/data/config.yaml
    touch /tmp/stamp
    /opt/hermes/.venv/bin/python /w/drive.py /w/voice.ogg; rc=$?
    echo "drive exit $rc"
    echo "-- dirs with files newer than start (outside /proc,/sys,/tmp):"
    find / -xdev \( -path /proc -o -path /sys -o -path /tmp \) -prune -o -type f -newer /tmp/stamp -print 2>/dev/null \
      | awk -F/ "{print \"/\"\$2\"/\"\$3\"/\"\$4}" | sort | uniq -c | sort -rn | head -15
    find /opt/data -type f -newer /tmp/stamp -print 2>/dev/null | awk -F/ "{print \"/\"\$2\"/\"\$3\"/\"\$4\"/\"\$5}" | sort | uniq -c | sort -rn | head -15
    du -sh /opt/data /opt/data/* /opt/hermes/.venv 2>/dev/null | sort -h | tail -8
    exit $rc'
  rc=$?
  echo "container $1 exit $rc, OOMKilled=$(docker inspect -f '{{.State.OOMKilled}}' $TAG-$1)"
  return $rc
}
echo "== run A: first voice message on a fresh /opt/data"
run a "$CFG"; A=$?
echo "== run B: fresh container (restart), same /opt/data volume"
run b "$CFG"; B=$?
echo "A=$A B=$B"
[ $A -eq 0 ] && [ $B -eq 0 ]
