#!/usr/bin/env bash
# Spike: does the Complexity Router's classifier call to ollama/clef:cloud pass
# VK governance / the catalog check? Exits 0 only when, for a VK whose
# allowed_models lists clef:cloud explicitly, every chat request triggers a
# classifier POST /v1/systemone upstream and lands on the tier's model.
set -u
W=$(mktemp -d)
cat > "$W/mock.py" <<'MOCK'
"""Mock Ollama upstream: logs every request, answers decision, chat, models."""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CATALOG = ["gpt-oss:120b-cloud", "deepseek-v4.1-flash", "mistral-large-4"]

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _log(self, body):
        print(json.dumps({"method": self.command, "path": self.path,
                          "auth": self.headers.get("Authorization", "")[:20], "body": body[:600]}), flush=True)

    def do_GET(self):
        self._log("")
        if self.path.startswith("/v1/models"):
            return self._send(200, {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "ollama"} for m in CATALOG]})
        self._send(404, {"error": {"message": "nope"}})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n).decode()
        self._log(body)
        req = json.loads(body or "{}")
        if self.path.startswith("/v1/systemone"):
            text = json.dumps(req.get("state"))
            tier = "COMPLEX" if "proof" in text.lower() else "SIMPLE"
            return self._send(200, {"model": req.get("model", "?"),
                                    "answers": {name: {"type": "choice", "choice": tier if name == "complexity_tier" else sorted((q.get("criteria") or {"a": 1}))[0], "confidence": 0.9} for name, q in (req.get("questions") or {}).items()},
                                    "usage": {"input_tokens": 10, "output_tokens": 1}})
        if self.path.startswith("/v1/chat/completions"):
            m = req.get("model")
            return self._send(200, {"id": "x", "object": "chat.completion", "created": int(time.time()), "model": m,
                                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "served-by:" + str(m)}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        self._send(404, {"error": {"message": "unknown path"}})

ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
MOCK
cat > "$W/config.json" <<'CONF'
{
  "$schema": "https://www.getbifrost.ai/schema",
  "client": {
    "drop_excess_requests": false,
    "enable_logging": true,
    "enforce_auth_on_inference": true
  },
  "config_store": {
    "enabled": true,
    "type": "sqlite",
    "config": {
      "path": "/app/data/config.db"
    }
  },
  "logs_store": {
    "enabled": true,
    "type": "sqlite",
    "config": {
      "path": "/app/data/logs.db"
    }
  },
  "providers": {
    "ollama": {
      "keys": [
        {
          "name": "ollama-mock",
          "value": "mock-key",
          "models": [
            "*"
          ],
          "weight": 1.0,
          "ollama_key_config": {
            "url": "http://bf2-mock:8000"
          }
        }
      ],
      "network_config": {
        "base_url": "http://bf2-mock:8000",
        "default_request_timeout_in_seconds": 20,
        "max_retries": 0,
        "allow_private_network": true
      }
    }
  },
  "governance": {
    "virtual_keys": [
      {
        "id": "vk-explicit",
        "name": "router-explicit",
        "value": "sk-bf-explicit-0000000000000000",
        "is_active": true,
        "provider_configs": [
          {
            "provider": "ollama",
            "weight": 1.0,
            "allowed_models": [
              "clef:cloud",
              "gpt-oss:120b-cloud",
              "deepseek-v4.1-flash",
              "mistral-large-4"
            ],
            "key_ids": [
              "*"
            ]
          }
        ]
      },
      {
        "id": "vk-star",
        "name": "router-star",
        "value": "sk-bf-star-00000000000000000000",
        "is_active": true,
        "provider_configs": [
          {
            "provider": "ollama",
            "weight": 1.0,
            "allowed_models": [
              "*"
            ],
            "key_ids": [
              "*"
            ]
          }
        ]
      }
    ],
    "complexity_analyzer_config": {
      "classifier": "decision",
      "keywords": {
        "simple_keywords": [
          "hello"
        ],
        "medium_keywords": [
          "explain"
        ],
        "complex_keywords": [
          "prove"
        ]
      },
      "decision": {
        "provider": "ollama",
        "model": "clef:cloud",
        "timeout": "5s"
      }
    },
    "routing_rules": [
      {
        "id": "r-simple",
        "name": "tier-simple",
        "enabled": true,
        "scope": "global",
        "priority": 1,
        "cel_expression": "complexity_tier == \"SIMPLE\"",
        "targets": [
          {
            "provider": "ollama",
            "model": "gpt-oss:120b-cloud",
            "weight": 1.0
          }
        ]
      },
      {
        "id": "r-medium",
        "name": "tier-medium",
        "enabled": true,
        "scope": "global",
        "priority": 2,
        "cel_expression": "complexity_tier == \"MEDIUM\"",
        "targets": [
          {
            "provider": "ollama",
            "model": "deepseek-v4.1-flash",
            "weight": 1.0
          }
        ]
      },
      {
        "id": "r-complex",
        "name": "tier-complex",
        "enabled": true,
        "scope": "global",
        "priority": 3,
        "cel_expression": "complexity_tier == \"COMPLEX\"",
        "targets": [
          {
            "provider": "ollama",
            "model": "mistral-large-4",
            "weight": 1.0
          }
        ]
      }
    ]
  }
}
CONF
chmod -R 777 "$W"
cleanup() { docker rm -f bf2-bifrost bf2-mock >/dev/null 2>&1; docker network rm bf2-net >/dev/null 2>&1; }
cleanup; trap cleanup EXIT
docker network create bf2-net >/dev/null
docker run -d --name bf2-mock --network bf2-net -v "$W/mock.py:/mock.py:ro" docker.io/library/python:3.12-alpine python -u /mock.py >/dev/null
docker run -d --name bf2-bifrost --network bf2-net -p 18081:8080 -e APP_HOST=0.0.0.0 -e APP_PORT=8080 -v "$W:/app/data" docker.io/maximhq/bifrost:v2.3.1 >/dev/null
for i in $(seq 60); do curl -sf localhost:18081/health >/dev/null && break; sleep 1; done
B=http://localhost:18081
chat() { curl -s -X POST $B/v1/chat/completions -H "x-bf-vk: $1" -H 'Content-Type: application/json' \
  -d "{\"model\":\"ollama/deepseek-v4.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"$2\"}]}"; }
dec() { curl -s -X POST $B/v1/decisions -H "x-bf-vk: $1" -H 'Content-Type: application/json' \
  -d '{"model":"ollama/clef:cloud","input":"hi","questions":[{"type":"choice","name":"q","instructions":"pick","choices":[{"value":"a","description":"a"},{"value":"b","description":"b"}]}]}'; }
fail=0
for vk in explicit star; do
  key=$( [ $vk = explicit ] && echo sk-bf-explicit-0000000000000000 || echo sk-bf-star-00000000000000000000 )
  for p in "hello there, what time is it" "write a rigorous proof that sqrt 2 is irrational"; do
    before=$(docker logs bf2-mock 2>&1 | grep -c '"/v1/systemone"')
    r=$(chat $key "$p"); after=$(docker logs bf2-mock 2>&1 | grep -c '"/v1/systemone"')
    served=$(echo "$r" | python3 -c 'import sys,json
try: d=json.load(sys.stdin); print(d.get("model") or d.get("error",{}).get("message") or d)
except Exception as e: print("unparsed")')
    echo "== vk=$vk prompt=\"$p\" classifier_calls_upstream=$((after-before)) served=$served"
    echo "   extra_fields: $(echo "$r" | python3 -c 'import sys,json;print(json.dumps(json.load(sys.stdin).get("extra_fields"))[:600])')"
    if [ $vk = explicit ]; then
      want=$( [[ "$p" == *proof* ]] && echo mistral-large-4 || echo gpt-oss:120b-cloud )
      [ $((after-before)) -ge 1 ] && [[ "$served" == *"$want"* ]] || { echo "   FAIL: wanted classifier call and $want"; fail=1; }
    fi
  done
  echo "== vk=$vk direct POST /v1/decisions ollama/clef:cloud: $(dec $key | head -c 400)"
done
echo "== mock upstream log"; docker logs bf2-mock 2>&1 | cut -c1-300
echo "== bifrost log (filtered)"; docker logs bf2-bifrost 2>&1 | grep -v migration | grep -iE 'complex|decision|routing|clef|model|key|error' | cut -c1-400 | tail -30
exit $fail
