"""Stand-in for embark: logs every request body and validates it with
embark v0.2.1's own pydantic request models, answering in embark's shapes."""
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pydantic import ValidationError
from embark.routes.rerank import RerankRequest
from embark.routes.embeddings import EmbeddingRequest

LOG = "/tmp/stub.log"

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length", 0)))
        entry = {"path": self.path, "auth": self.headers.get("authorization", "")[:7], "body": raw.decode(errors="replace")}
        status, out = 404, {"error": "not found"}
        try:
            if self.path in ("/v1/rerank", "/rerank"):
                req = RerankRequest.model_validate_json(raw)
                docs = req.texts()
                status, out = 200, {"model": req.model, "results": [
                    {"index": i, "relevance_score": float(len(docs) - i)} for i in range(len(docs))]}
            elif self.path == "/v1/embeddings":
                req = EmbeddingRequest.model_validate_json(raw)
                status, out = 200, {"object": "list", "model": req.model,
                    "data": [{"object": "embedding", "index": i, "embedding": [0.1] * 384} for i, _ in enumerate(req.texts())],
                    "usage": {"prompt_tokens": 3, "total_tokens": 3}}
        except ValidationError as e:
            status, out = 422, {"error": e.errors(include_url=False)}
        entry["embark_status"] = status
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        data = json.dumps(out, default=str).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *a):
        pass

ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
