"""Snapshot the registry by its API: tags, manifest digests, layer digests and sizes.

Usage: snapshot.py OUT_FILE [--verify BEFORE_FILE]. Downloads only manifests and
config blobs (small); layers are checked with HEAD (digest and size, no body).
With --verify it also pulls each manifest by digest and compares to BEFORE.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

R = "https://registry.lab.orangecluster.nl"
AUTH = "Basic " + __import__("base64").b64encode(f"push:{os.environ['REG_PASS']}".encode()).decode()
ACCEPT = ", ".join([
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.index.v1+json",
])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


opener = urllib.request.build_opener(NoRedirect)


def req(path: str, method: str = "GET") -> tuple[bytes, object]:
    """Registry call; a blob redirect is followed to the presigned S3 URL without our auth."""
    r = urllib.request.Request(R + path, method=method, headers={"Authorization": AUTH, "Accept": ACCEPT})
    try:
        resp = opener.open(r, timeout=120)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        location = e.headers["Location"]
        resp = urllib.request.urlopen(urllib.request.Request(location, method=method), timeout=120)
    with resp:
        return (resp.read() if method == "GET" else b""), resp.headers


snap: dict[str, dict[str, object]] = {}
for repo in sorted(json.loads(req("/v2/_catalog?n=1000")[0])["repositories"]):
    for tag in sorted(json.loads(req(f"/v2/{repo}/tags/list")[0])["tags"] or []):
        body, headers = req(f"/v2/{repo}/manifests/{tag}")
        digest = headers["Docker-Content-Digest"]
        manifest = json.loads(body)
        layers = []
        for layer in manifest.get("layers", []):
            _, h = req(f"/v2/{repo}/blobs/{layer['digest']}", method="HEAD")
            layers.append([layer["digest"], int(h["Content-Length"])])
        config = manifest.get("config", {}).get("digest")
        config_sha = "sha256:" + hashlib.sha256(req(f"/v2/{repo}/blobs/{config}")[0]).hexdigest() if config else None
        by_digest = "sha256:" + hashlib.sha256(req(f"/v2/{repo}/manifests/{digest}")[0]).hexdigest()
        snap[f"{repo}:{tag}"] = {"manifest": digest, "by_digest": by_digest, "config": config, "config_sha": config_sha, "layers": layers}

json.dump(snap, open(sys.argv[1], "w"), indent=1, sort_keys=True)
total = sum(size for v in snap.values() for _, size in v["layers"])
print(f"{len(snap)} tags, {sum(len(v['layers']) for v in snap.values())} layers, {total} layer bytes")
bad = [k for k, v in snap.items() if v["by_digest"] != v["manifest"] or (v["config"] and v["config_sha"] != v["config"])]
print("digest mismatches:", bad)
if "--verify" in sys.argv:
    before = json.load(open(sys.argv[sys.argv.index("--verify") + 1]))
    print("identical to before:", before == snap, "| tags before/after:", len(before), len(snap))
    sys.exit(0 if before == snap and not bad else 1)
sys.exit(1 if bad else 0)
