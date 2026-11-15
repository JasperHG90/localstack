#!/usr/bin/env bash
# Times clef:cloud decision calls through Bifrost and checks the three tier
# models answer a chat call there. Needs BIFROST_VK, a virtual key that can
# call those models. Exits 0 only when every call answers and the slowest clef
# call is under TIMEOUT_MS (default 5000), the classifier timeout to set.
set -euo pipefail
: "${BIFROST_VK:?set BIFROST_VK to a Bifrost virtual key}"
TIMEOUT_MS=${TIMEOUT_MS:-5000}
BASE=${BIFROST_URL:-https://bifrost.lab.orangecluster.nl}
auth=(-H "x-bf-vk: $BIFROST_VK" -H 'Content-Type: application/json')
fail=0
worst=0

prompts=("Say hi." "Summarise this paragraph in one line: the cat sat on the mat." \
  "Design a sharded, multi-region event store with exactly-once delivery and explain the trade-offs." \
  "Write a haiku about rain." "Prove that there are infinitely many primes and then generalise the argument.")
for p in "${prompts[@]}"; do
  input=$(printf '%s' "$p" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
  body='{"model":"ollama/clef:cloud","input":'$input',"questions":[{"name":"tier","type":"choice","instructions":"How complex is this task for a language model?","choices":[{"value":"SIMPLE"},{"value":"MEDIUM"},{"value":"COMPLEX"}]}]}'
  out=$(curl -s -m 30 -w '\n%{http_code} %{time_total}' "${auth[@]}" -d "$body" "$BASE/v1/decisions")
  code=$(tail -1 <<<"$out" | cut -d' ' -f1)
  ms=$(tail -1 <<<"$out" | awk '{printf "%d", $2 * 1000}')
  answer=$(head -n -1 <<<"$out" | head -c 300)
  echo "clef  $code ${ms}ms  prompt=\"${p:0:40}\"  $answer"
  [ "$code" = 200 ] || fail=1
  [ "$ms" -gt "$worst" ] && worst=$ms
done
echo "clef worst: ${worst}ms (timeout under test: ${TIMEOUT_MS}ms)"
[ "$worst" -lt "$TIMEOUT_MS" ] || fail=1

for m in gpt-oss:120b-cloud deepseek-v4.1-flash mistral-large-4; do
  body='{"model":"ollama/'$m'","messages":[{"role":"user","content":"Reply with the word ok."}],"max_tokens":8}'
  out=$(curl -s -m 60 -o /dev/null -w '%{http_code} %{time_total}' "${auth[@]}" -d "$body" "$BASE/v1/chat/completions")
  echo "chat  $m -> $out"
  [ "${out%% *}" = 200 ] || fail=1
done
exit $fail
