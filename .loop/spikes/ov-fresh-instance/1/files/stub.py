# OpenAI-compatible stand-in for Bifrost: embeddings (384-d, hashed),
# rerank, and chat completions. Enough for OpenViking to boot, index and search.
import hashlib, json, math, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIM = 384

def vec(text):
    out = []
    i = 0
    while len(out) < DIM:
        h = hashlib.sha256(f"{i}:{text}".encode()).digest()
        out += [(b - 127.5) / 127.5 for b in h]
        i += 1
    out = out[:DIM]
    n = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / n for x in out]

class H(BaseHTTPRequestHandler):
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"data": [{"id": "stub", "object": "model"}]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(n) or b"{}")
        p = self.path
        if "embeddings" in p:
            inp = req.get("input")
            inp = [inp] if isinstance(inp, str) else inp
            self._send({"object": "list", "model": "stub",
                        "data": [{"object": "embedding", "index": i, "embedding": vec(str(t))} for i, t in enumerate(inp)],
                        "usage": {"prompt_tokens": 1, "total_tokens": 1}})
        elif "rerank" in p:
            docs = req.get("documents") or []
            self._send({"results": [{"index": i, "relevance_score": 0.9 - i * 0.01} for i in range(len(docs))]})
        else:
            self._send({"id": "x", "object": "chat.completion", "created": int(time.time()), "model": "stub",
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": "{}"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    def log_message(self, fmt, *a):
        sys.stderr.write("stub " + (fmt % a) + "\n")

ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
