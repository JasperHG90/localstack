#!/usr/bin/env bash
# Spike bifrost-update-2-6 risk 2: does Bifrost complete TLS to ollama.com, Gemini
# (default base) and typesafe (default https://api.typesafe.ai) on 2.6.0, with
# 2.3.1 as control? Provider blocks copied from services/bifrost.hcl; keys are
# BOGUS. An upstream HTTP error (401/403/400...) means TLS passed; an
# x509/certificate/tls error means it failed. Exit 0 only if no provider on
# 2.6.0 shows a TLS error and each got an upstream HTTP answer.
# Negative control per version: the same ollama block pointed at
# https://untrusted-root.badssl.com must produce an x509 error, which proves a
# TLS failure on this path is visible in the response (and is not masked as
# ollama's "upstream_credentials_exhausted", which Bifrost returns only after
# every key got a permanent per-key HTTP error from upstream).
set -u
S=/home/vscode/spike-scratch/bifrost-3
OUT=$(mktemp -d)
cleanup() { docker rm -f spike-bf3 >/dev/null 2>&1; }
trap cleanup EXIT
sed 's#https://ollama.com#https://untrusted-root.badssl.com#g' "$S/config.json" > "$OUT/bad.json"
for v in 2.3.1 2.6.0; do
 for cfg in real control; do
  cleanup
  src="$S/config.json"; [ "$cfg" = control ] && src="$OUT/bad.json"
  docker create --name spike-bf3 -p 127.0.0.1:18089:8080 \
    -e OLLAMA_KEY_PERSONAL=bogus-ollama-1 -e OLLAMA_KEY_XEBIA=bogus-ollama-2 \
    -e GEMINI_API_KEY=bogus-gemini -e TYPESAFE_API_KEY=bogus-typesafe \
    "maximhq/bifrost:v$v" >/dev/null
  docker cp "$src" spike-bf3:/app/data/config.json
  docker start spike-bf3 >/dev/null
  for i in $(seq 1 60); do curl -sf http://127.0.0.1:18089/health >/dev/null && break; sleep 0.5; done
  call() { # name path body
    curl -s -m 60 -o "$OUT/$v.$1.body" -w '%{http_code}' -H 'content-type: application/json' \
      -X POST "http://127.0.0.1:18089$2" -d "$3" > "$OUT/$v.$1.code"
  }
  if [ "$cfg" = control ]; then
    call control /v1/chat/completions '{"model":"ollama/gpt-oss:120b","messages":[{"role":"user","content":"hi"}]}'
    echo "=== bifrost $v negative control (ollama -> untrusted-root.badssl.com): gateway HTTP $(cat "$OUT/$v.control.code")"
    cat "$OUT/$v.control.body"; echo
    continue
  fi
  call ollama /v1/chat/completions '{"model":"ollama/gpt-oss:120b","messages":[{"role":"user","content":"hi"}]}'
  call gemini /v1/chat/completions '{"model":"gemini/gemini-2.5-flash","messages":[{"role":"user","content":"hi"}]}'
  call typesafe /v1/decisions '{"model":"typesafe/jev-latest","input":"Say hi.","questions":[{"name":"tier","type":"choice","instructions":"How complex?","choices":[{"value":"SIMPLE"},{"value":"MEDIUM"},{"value":"COMPLEX"}]}]}'
  echo "=== bifrost $v ==="
  for p in ollama gemini typesafe; do
    echo "--- $p: gateway HTTP $(cat "$OUT/$v.$p.code")"; cat "$OUT/$v.$p.body"; echo
  done
  echo "--- $v container log lines mentioning tls/x509/certificate:"
  docker logs spike-bf3 2>&1 | grep -i -E 'x509|certificate|tls' | head -20 || true
 done
done
python3 - "$OUT" <<'PY'
import json, re, sys
out = sys.argv[1]
tls = re.compile(r"x509|certificate|tls|handshake", re.I)
ok = True
for v in ("2.3.1", "2.6.0"):
    ctl = open(f"{out}/{v}.control.body").read()
    seen = bool(re.search(r"x509", ctl))
    print(f"{v} control: {'x509 error visible' if seen else 'NO x509 error (control broken)'}")
    ok = ok and seen
    for p in ("ollama", "gemini", "typesafe"):
        body = open(f"{out}/{v}.{p}.body").read()
        try:
            err = json.loads(body).get("error") or {}
        except Exception:
            err = {}
        j = json.loads(body) if body.strip().startswith("{") else {}
        up = j.get("status_code") or (err.get("status_code") if isinstance(err, dict) else None)
        etype = (err.get("type") if isinstance(err, dict) else None) or ""
        if etype == "provider_connection_failed":
            up = None
        bad = bool(tls.search(body))
        verdict = "TLS FAIL" if bad else ("TLS ok (HTTP %s, %s)" % (up, etype) if up else "UNCLEAR (no upstream status)")
        print(f"{v} {p}: {verdict}")
        if v == "2.6.0" and (bad or not up):
            ok = False
print("risk does not hold on 2.6.0" if ok else "RISK HOLDS OR UNANSWERED on 2.6.0")
sys.exit(0 if ok else 1)
PY
