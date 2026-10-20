"""Make and remove a throwaway directory through OpenViking's API; print each status."""
import json
import os
import urllib.parse
import urllib.request

U = "https://openviking-api.lab.orangecluster.nl"
H = {"Authorization": f"Bearer {os.environ['OV_TOKEN']}", "Content-Type": "application/json"}
uri = "viking://resources/seaweedfs-cutover-check"


def call(method: str, path: str, body: dict | None = None, **q: str) -> str:
    url = f"{U}{path}" + (f"?{urllib.parse.urlencode(q)}" if q else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=H)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return f"{r.status} {r.read()[:200].decode()}"
    except urllib.error.HTTPError as e:
        return f"{e.code} {e.read()[:200].decode()}"


import sys
if sys.argv[1] == "make":
    print("mkdir:", call("POST", "/api/v1/fs/mkdir", {"uri": uri}))
    print("stat:", call("GET", "/api/v1/fs/stat", uri=uri))
else:
    print("delete:", call("DELETE", "/api/v1/fs", uri=uri, recursive="true"))
