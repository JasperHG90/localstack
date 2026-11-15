#!/usr/bin/env bash
# Asks ollama/clef:cloud one choice question through Bifrost's /v1/decisions
# and appends the response to results.txt. One case per recorded outcome:
#   bare-strings  choices as bare strings, no key   -> 400 Invalid request payload
#   no-key        choices as objects, no key        -> 401 virtual_key_required
#   keyed         choices as objects, key from $BIFROST_VK
#                 (with the Hermes key)             -> 403 model_blocked
# BIFROST_URL overrides the gateway, for tests.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
URL=${BIFROST_URL:-https://bifrost.lab.orangecluster.nl}/v1/decisions
case=${1:-}

object_choices='[{"value":"simple"},{"value":"medium"},{"value":"complex"}]'
headers=(-H 'Content-Type: application/json')
case $case in
  bare-strings) choices='["simple","medium","complex"]' ;;
  no-key) choices=$object_choices ;;
  keyed)
    if [ -z "${BIFROST_VK:-}" ]; then
      echo "decide.sh keyed: set BIFROST_VK to a Bifrost virtual key" >&2
      exit 2
    fi
    choices=$object_choices
    headers+=(-H "x-bf-vk: $BIFROST_VK")
    ;;
  *)
    echo "usage: decide.sh bare-strings|no-key|keyed" >&2
    exit 2
    ;;
esac

body='{"model":"ollama/clef:cloud","input":"Write a haiku about cats.","questions":[{"name":"tier","type":"choice","instructions":"How complex is this task?","choices":'$choices'}]}'
response=$(curl -s -m 60 -w ' HTTP %{http_code}' "${headers[@]}" -d "$body" "$URL")
echo "$(date -u +%FT%TZ) $case: ${response//$'\n'/}" | tee -a "$HERE/results.txt"
