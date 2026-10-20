"""Fake OIDC issuer (spike-ovimg copy: overviews in the real H3-link format, image calls counted apart) (port 8000) and fake Bifrost (port 8080) for the spike.
Embeddings and rerank scores are bag-of-words hashes, so a title query lands near its file.
GET /counts on 8080 returns request counts per path and model."""
import collections, hashlib, json, math, re, sys, threading, time
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
COUNTS = collections.Counter()
LOCK = threading.Lock()


def vec(text):
    v = [0.0] * 384
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        v[int.from_bytes(hashlib.sha256(w.encode()).digest()[:4], "big") % 384] += 1.0
    v[0] += 0.01
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


VOCAB = ("pelican heron osprey puffin gannet cormorant albatross kestrel lighthouse windmill harbour "
         "quarry viaduct glacier orchard canal striped copper granite velvet amber cobalt crimson ivory "
         "diagram sketch blueprint chart poster etching mosaic woodcut").split()


def img_summary(msgs):
    # The image prompt carries no file name, so the reply is derived from the image bytes.
    d = hashlib.sha256(msgs.encode()).digest()
    words = [VOCAB[b % len(VOCAB)] for b in d[:5]]
    return "The image shows " + " ".join(words) + "."


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
        if u.path == "/counts":
            with LOCK:
                return self.send(dict(COUNTS))
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
        kind = "embeddings" if p.endswith("/embeddings") else "rerank" if p.endswith("/rerank") else \
            "chat" if p.endswith("/chat/completions") else p
        prompt = "\n".join(
            (m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content")))
            for m in (body.get("messages") or []) if isinstance(m, dict))
        entries = re.findall(r"^- (.+?) \(link: (viking://input_sample_[fc]\d+)\): ?(.*)$", prompt, re.M)
        has_img = "image_url" in json.dumps(body.get("messages", ""))
        if kind == "chat":
            kind = "chat-overview" if entries else ("chat-image" if has_img else "chat-file")
        with LOCK:
            COUNTS[f"{kind} {body.get('model')}"] += 1
        if kind == "embeddings":
            inp = body.get("input")
            inp = [inp] if isinstance(inp, str) else inp
            return self.send({"object": "list", "model": body.get("model"),
                              "data": [{"object": "embedding", "index": i, "embedding": vec(str(t))}
                                       for i, t in enumerate(inp)],
                              "usage": {"prompt_tokens": 1, "total_tokens": 1}})
        if kind == "rerank":
            docs = body.get("documents") or []
            q = vec(str(body.get("query", "")))
            texts = [d.get("text", json.dumps(d)) if isinstance(d, dict) else str(d) for d in docs]
            return self.send({"results": [{"index": i, "relevance_score": sum(a * b for a, b in zip(q, vec(t)))}
                                          for i, t in enumerate(texts)]})
        if kind == "chat-overview":
            # Same shape as the real overviews in the old bucket: H2 sections, then one
            # "### [name](link)" heading per entry under Detailed Description.
            out = (f"# dir\n\nThis directory holds {len(entries)} entries.\n\n## Directory Coverage\n\n"
                   f"Total direct entries: {len(entries)}. All direct entries are represented in the summaries below.\n\n"
                   "## Quick Navigation\n\nWhat do you want to learn?\n"
                   + "".join(f"- Read about {n} \u2192 [{n}]({ph})\n" for n, ph, _ in entries)
                   + "\n## Detailed Description\n\n"
                   + "\n".join(f"### [{n}]({ph})\n\n{sm[:400]}\n" for n, ph, sm in entries))
            return self.send({"id": "x", "object": "chat.completion", "created": 0, "model": body.get("model"),
                              "choices": [{"index": 0, "finish_reason": "stop",
                                           "message": {"role": "assistant", "content": out}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        if kind == "chat-image":
            return self.send({"id": "x", "object": "chat.completion", "created": 0, "model": body.get("model"),
                              "choices": [{"index": 0, "finish_reason": "stop",
                                           "message": {"role": "assistant",
                                                       "content": img_summary(json.dumps(body.get("messages", "")))}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        if kind == "chat-file":
            text = json.dumps(body.get("messages", ""))[-400:]
            words = " ".join(re.findall(r"[A-Za-z]{4,}", text)[:30])
            return self.send({"id": "x", "object": "chat.completion", "created": 0, "model": body.get("model"),
                              "choices": [{"index": 0, "finish_reason": "stop",
                                           "message": {"role": "assistant",
                                                       "content": "Summary of the content. " + words}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        self.send({"error": "nf"}, 404)


for port in (8000, 8080):
    s = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
print("fake ready", flush=True)
threading.Event().wait()
