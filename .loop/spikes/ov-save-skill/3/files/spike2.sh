#!/usr/bin/env bash
# Spike: with stt.provider: local set in config.yaml, does hermes 0.22.2-1 lazy-install faster-whisper and transcribe an .ogg under 2048 MB, and does it survive a restart?
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice
IMG=ghcr.io/jasperhg90/hermes:0.22.2-1
TAG=ovsave-voice-$$
VOL=$TAG-data
W=$(mktemp -d "$D/run.XXXX"); chmod 755 "$W"
cleanup() { docker rm -f $TAG-tts $TAG-z $TAG-a $TAG-b >/dev/null 2>&1; docker volume rm $VOL >/dev/null 2>&1; }
trap cleanup EXIT
cp "$D/drive.py" "$W/drive.py"; CFG="${CFG:-model:\n  provider: bifrost\nstt:\n  provider: local\n}"

echo "== make voice.ogg (espeak-ng -> ffmpeg libopus, as Telegram sends)"
docker run --rm --name $TAG-tts -v "$W:/w" debian:trixie-slim sh -c '
  apt-get update -qq >/dev/null && apt-get install -y -qq espeak-ng ffmpeg >/dev/null 2>&1 &&
  espeak-ng -s 140 -w /w/v.wav "The quick brown fox jumps over the lazy dog. Please save this link." &&
  ffmpeg -loglevel error -i /w/v.wav -ac 1 -ar 48000 -c:a libopus -b:a 32k /w/voice.ogg && chmod 644 /w/voice.ogg' || exit 10
ls -l "$W/voice.ogg"

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
echo "== run 0: deployed config (no stt section), fresh /opt/data"
run z "model:\n  provider: bifrost\n"
docker volume rm $VOL >/dev/null; docker volume create $VOL >/dev/null
echo "== run A: stt.provider local, first voice message on a fresh /opt/data"
run a "$CFG"; A=$?
echo "== run B: fresh container (restart), same /opt/data volume"
run b "$CFG"; B=$?
echo "A=$A B=$B"
[ $A -eq 0 ] && [ $B -eq 0 ]
