import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        inp = raw.get("input", [])
        n = 1 if isinstance(inp, str) else len(inp)
        out = json.dumps({"object": "list", "model": raw.get("model"),
            "data": [{"object": "embedding", "index": i, "embedding": [0.1] * 8} for i in range(n)],
            "usage": {"prompt_tokens": 1, "total_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass
ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
