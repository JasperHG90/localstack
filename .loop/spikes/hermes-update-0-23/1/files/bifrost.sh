#!/bin/sh
# Spike hermes-update-0-23 risk 3: does the bifrost model-provider plugin, taken
# verbatim from deployments/applications/services/hermes.hcl, load in
# nousresearch/hermes-agent:v0.23.4 as provider `bifrost`, and does a model
# call reach a stub Bifrost on 127.0.0.1:8080? Exits 0 only if both hold.
set -eu
IMAGE=nousresearch/hermes-agent:v0.23.4
HCL="$(git rev-parse --show-toplevel)/deployments/applications/services/hermes.hcl"
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
chmod 755 "$W"
echo "image: $(docker image inspect "$IMAGE" --format '{{.Id}} {{.Architecture}}')"

cat > "$W/extract.py" <<'PY'
"""Write the bifrost plugin files from hermes.hcl into OUT/model-providers/bifrost/."""
import re, sys, pathlib
hcl, out = sys.argv[1], pathlib.Path(sys.argv[2])
t = open(hcl).read()
n = 0
for m in re.finditer(r'\nEOF\n\s*\n\s*destination = "local/(model-providers/bifrost/[^"]+)"', t):
    start = t.rfind('<<EOF\n', 0, m.start()) + len('<<EOF\n')
    body = t[start:m.start()] + '\n'
    assert '${' not in body and '%{' not in body, 'template interpolation in plugin body'
    p = out / m.group(1); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
    print('wrote', p, len(body)); n += 1
assert n == 2, n
PY
cat > "$W/check.py" <<'PY'
"""Runs inside the hermes-agent image: is the user plugin `bifrost` registered and resolvable?"""
import logging, warnings
logging.basicConfig(level=logging.WARNING)
warnings.simplefilter("default")
from providers import get_provider_profile, list_providers, provider_source
p = get_provider_profile("bifrost")
assert p is not None, "bifrost not registered"
print("profile:", p.name, p.base_url, p.env_vars, "source:", provider_source("bifrost"))
assert provider_source("bifrost") == "user", provider_source("bifrost")
assert get_provider_profile("bifrost-gateway") is p, "alias missing"
assert "bifrost" in [x.name for x in list_providers()], "not in list_providers"
from hermes_cli.auth import PROVIDER_REGISTRY, resolve_provider
print("auth registry has bifrost:", "bifrost" in PROVIDER_REGISTRY, "resolve:", resolve_provider("bifrost"))
assert "bifrost" in PROVIDER_REGISTRY
from hermes_cli.runtime_provider import resolve_runtime_provider
rt = resolve_runtime_provider(requested="bifrost")
print("runtime:", {k: rt.get(k) for k in ("provider", "base_url", "api_mode")}, "key set:", bool(rt.get("api_key")))
assert rt.get("base_url", "").startswith("http://127.0.0.1:8080/v1"), rt
print("CHECK OK")
PY
cat > "$W/stub.py" <<'PY'
"""Stand-in for Bifrost on 127.0.0.1:8080: OpenAI chat completions (plain and SSE), logs each request."""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
REPLY = "STUB-BIFROST-REPLY"
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _log(self, body=None):
        rec = {"method": self.command, "path": self.path, "auth": self.headers.get("Authorization"),
               "model": (body or {}).get("model"), "stream": (body or {}).get("stream")}
        print("STUB", json.dumps(rec), file=sys.stderr, flush=True)
    def do_GET(self):
        self._log()
        data = json.dumps({"object": "list", "data": [{"id": "ollama/deepseek-v4.1-flash", "object": "model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self._log(body)
        model, now = body.get("model", "x"), int(time.time())
        usage = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        if body.get("stream"):
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for delta, fin in (({"role": "assistant", "content": REPLY}, None), ({}, "stop")):
                ch = {"id": "c1", "object": "chat.completion.chunk", "created": now, "model": model,
                      "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
                self.wfile.write(f"data: {json.dumps(ch)}\n\n".encode())
            ch = {"id": "c1", "object": "chat.completion.chunk", "created": now, "model": model, "choices": [], "usage": usage}
            self.wfile.write(f"data: {json.dumps(ch)}\n\ndata: [DONE]\n\n".encode()); self.wfile.flush()
            return
        data = json.dumps({"id": "c1", "object": "chat.completion", "created": now, "model": model, "usage": usage,
                           "choices": [{"index": 0, "finish_reason": "stop",
                                        "message": {"role": "assistant", "content": REPLY}}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
ThreadingHTTPServer(("127.0.0.1", 8080), H).serve_forever()
PY
cat > "$W/config.yaml" <<'EOF'
model:
  provider: "bifrost"
  default: "ollama/deepseek-v4.1-flash"
  context_length: 128000
EOF

python3 "$W/extract.py" "$HCL" "$W/plugins"
chmod -R a+rX "$W"

docker run --rm --user hermes -e HERMES_HOME=/tmp/h -e BIFROST_API_KEY=sk-test \
  -e HERMES_YOLO_MODE=true -v "$W:/src:ro" -w /opt/hermes \
  --entrypoint sh "$IMAGE" -c '
set -e
/opt/hermes/.venv/bin/python3 --version
mkdir -p /tmp/h/plugins
cp -r /src/plugins/model-providers /tmp/h/plugins/
cp /src/config.yaml /tmp/h/config.yaml
/opt/hermes/.venv/bin/python3 /src/check.py
/opt/hermes/.venv/bin/python3 /src/stub.py 2>/tmp/stub.log &
sleep 1
cd /tmp
out=$(timeout 90 hermes -z "Say hi" 2>&1) || { echo "$out"; echo "hermes -z failed"; exit 1; }
echo "hermes -z output: $out"
cat /tmp/stub.log
grep -q "\"path\": \"/v1/chat/completions\", \"auth\": \"Bearer sk-test\", \"model\": \"ollama/deepseek-v4.1-flash\"" /tmp/stub.log
printf "%s" "$out" | grep -q STUB-BIFROST-REPLY
echo "PASS: bifrost plugin loads and a model call reached the stub"
'
