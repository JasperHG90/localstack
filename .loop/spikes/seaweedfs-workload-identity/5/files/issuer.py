# Fake Nomad OIDC issuer: discovery, JWKS, and /mint?job=NAME for test JWTs.
import json, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import jwt
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa

ISS = "http://issuer:8080"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = json.loads(RSAAlgorithm.to_jwk(KEY.public_key()))
JWK.update(kid="k1", use="sig", alg="RS256")

class H(BaseHTTPRequestHandler):
    def send(self, body, ctype="application/json"):
        b = body.encode()
        self.send_response(200); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/.well-known/openid-configuration":
            self.send(json.dumps({"issuer": ISS, "jwks_uri": ISS + "/.well-known/jwks.json",
                "id_token_signing_alg_values_supported": ["RS256"], "response_types_supported": ["code"],
                "subject_types_supported": ["public"]}))
        elif u.path == "/.well-known/jwks.json":
            self.send(json.dumps({"keys": [JWK]}))
        elif u.path == "/mint":
            job = parse_qs(u.query)["job"][0]; now = int(time.time())
            claims = {"iss": ISS, "aud": ["seaweedfs"], "sub": f"global:default:{job}:{job}:{job}",
                "nomad_namespace": "default", "nomad_job_id": job, "nomad_task": job,
                "nomad_allocation_id": str(uuid.uuid4()), "iat": now, "nbf": now, "exp": now + 3600}
            self.send(jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"}), "text/plain")
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("0.0.0.0", 8080), H).serve_forever()
