"""Push a tiny OCI image to the registry, read it back by tag and digest, then delete it."""
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

R = "https://registry.lab.orangecluster.nl"
REPO = "seaweedfs-cutover-check"
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirect)
AUTH = "Basic " + base64.b64encode(f"push:{os.environ['REG_PASS']}".encode()).decode()


def call(method: str, url: str, body: bytes = b"", ctype: str = "application/octet-stream", accept: str = "") -> tuple[int, object, bytes]:
    url = url if url.startswith("http") else R + url
    h = {"Authorization": AUTH, "Content-Type": ctype}
    if accept:
        h["Accept"] = accept
    try:
        with OPENER.open(urllib.request.Request(url, data=body or None, method=method, headers=h), timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        if e.code in (302, 307) and method == "GET":
            # A blob redirects to a presigned S3 URL, which must get no registry auth.
            with urllib.request.urlopen(e.headers["Location"], timeout=60) as r:
                return r.status, r.headers, r.read()
        return e.code, e.headers, e.read()


def push_blob(data: bytes) -> str:
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    code, h, _ = call("POST", f"/v2/{REPO}/blobs/uploads/")
    assert code == 202, f"upload start {code}"
    loc = h["Location"]
    loc = (R + loc) if loc.startswith("/") else loc
    sep = "&" if "?" in loc else "?"
    code, _, body = call("PUT", f"{loc}{sep}digest={digest}", data)
    assert code == 201, f"blob put {code} {body[:200]!r}"
    return digest


layer = f"seaweedfs cutover check {os.environ.get('STAMP', '')}".encode()
config = json.dumps({"architecture": "amd64", "os": "linux", "rootfs": {"type": "layers", "diff_ids": []}}).encode()
ld, cd = push_blob(layer), push_blob(config)
mt = "application/vnd.oci.image.manifest.v1+json"
manifest = json.dumps({"schemaVersion": 2, "mediaType": mt,
    "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": cd, "size": len(config)},
    "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar", "digest": ld, "size": len(layer)}]}).encode()
code, h, body = call("PUT", f"/v2/{REPO}/manifests/check", manifest, mt)
print("manifest put:", code)
md = h["Docker-Content-Digest"]
by_tag = call("GET", f"/v2/{REPO}/manifests/check", accept=mt)
by_digest = call("GET", f"/v2/{REPO}/manifests/{md}", accept=mt)
blob = call("GET", f"/v2/{REPO}/blobs/{ld}")
print("pull by tag:", by_tag[0], "| by digest:", by_digest[0], "| layer:", blob[0], blob[2] == layer)
ok = code == 201 and by_tag[0] == 200 and by_digest[0] == 200 and blob[0] == 200 and blob[2] == layer
if sys.argv[1:] == ["--delete"]:
    print("delete manifest:", call("DELETE", f"/v2/{REPO}/manifests/{md}")[0])
sys.exit(0 if ok else 1)
