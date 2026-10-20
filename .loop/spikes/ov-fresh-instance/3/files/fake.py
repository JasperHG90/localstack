"""Fake OIDC issuer (port 8000) and fake Bifrost (port 8080) for the spike."""
import hashlib, json, math, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwk, jwt

ISS = sys.argv[1]
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption()).decode()
PUB = jwk.construct(KEY.public_key().public_bytes(serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo).decode(), "RS256").to_dict()
PUB.update(kid="spike", use="sig", alg="RS256")
PUB = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in PUB.items()}


def vec(text):
    h = hashlib.sha256(text.encode()).digest()
    v = [((h[i % 32] + i) % 17) - 8.0 for i in range(384)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class H(BaseHTTPRequestHandler):
    def log_message(self, f, *a):
        sys.stderr.write("fake %s %s\n" % (self.server.server_port, f % a))

    def send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/.well-known/openid-configuration":
            return self.send({"issuer": ISS, "jwks_uri": ISS + "/keys"})
        if u.path == "/keys":
            return self.send({"keys": [PUB]})
        if u.path == "/mint":
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            now = int(time.time())
            claims = {"iss": ISS, "aud": "openviking", "sub": "spike", "iat": now, "exp": now + 3600}
            claims.update(q)
            tok = jwt.encode(claims, PEM, algorithm="RS256", headers={"kid": "spike"})
            return self.send({"token": tok})
        self.send({"error": "nf"}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        p = urlparse(self.path).path
        if p.endswith("/embeddings"):
            inp = body.get("input")
            inp = [inp] if isinstance(inp, str) else inp
            return self.send({"object": "list", "model": body.get("model"),
                              "data": [{"object": "embedding", "index": i, "embedding": vec(str(t))}
                                       for i, t in enumerate(inp)],
                              "usage": {"prompt_tokens": 1, "total_tokens": 1}})
        if p.endswith("/rerank"):
            docs = body.get("documents") or []
            return self.send({"results": [{"index": i, "relevance_score": 0.5} for i in range(len(docs))]})
        if p.endswith("/chat/completions"):
            return self.send({"id": "x", "object": "chat.completion", "created": 0, "model": body.get("model"),
                              "choices": [{"index": 0, "finish_reason": "stop",
                                           "message": {"role": "assistant", "content": "{}"}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        self.send({"error": "nf"}, 404)


for port in (8000, 8080):
    s = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
print("fake ready", flush=True)
threading.Event().wait()
