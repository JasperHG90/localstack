# Mock Ollama upstream: /v1/systemone answers complexity_tier from a marker in
# the user text, /v1/chat/completions echoes the model it received.
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = []


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/_log":
            return self._send(200, LOG)
        LOG.append({"method": "GET", "path": self.path})
        models = ["clef:cloud", "gpt-oss:120b-cloud", "deepseek-v4.1-flash", "mistral-large-4"]
        self._send(200, {"object": "list", "data": [{"id": x, "object": "model", "created": 0, "owned_by": "ollama"} for x in models]})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length", 0)))
        try:
            body = json.loads(raw)
        except Exception:
            body = {}
        entry = {"method": "POST", "path": self.path, "model": body.get("model")}
        if self.path.endswith("/v1/systemone"):
            state = json.dumps(body.get("state"))
            tier = "COMPLEX" if "ZZCOMPLEX" in state else "MEDIUM" if "ZZMEDIUM" in state else "SIMPLE"
            q = body.get("questions", {}).get("complexity_tier", {})
            entry.update(tier=tier, question_keys=list(body.get("questions", {})),
                         criteria_keys=list((q.get("criteria") or {}).keys()) if isinstance(q.get("criteria"), dict) else q.get("criteria"),
                         state=body.get("state"))
            LOG.append(entry)
            return self._send(200, {"model": body.get("model"), "answers": {
                "complexity_tier": {"type": "choice", "choice": tier, "confidence": 0.9}},
                "usage": {"input_tokens": 10, "output_tokens": 1}})
        if self.path.endswith("/chat/completions"):
            LOG.append(entry)
            return self._send(200, {
                "id": "x", "object": "chat.completion", "created": 0, "model": body.get("model"),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": "served-by:" + str(body.get("model"))}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        entry["body"] = raw[:500].decode(errors="replace")
        LOG.append(entry)
        self._send(404, {"error": "not found"})


ThreadingHTTPServer(("0.0.0.0", 11434), H).serve_forever()
