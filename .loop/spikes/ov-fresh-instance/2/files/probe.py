"""Spike probe. `oidc`: ls, mkdir, write, find, search as lab/jasper via a JWT.
`bootstrap`: create account lab with admin jasper via the root key. Exit 0 on all 2xx."""
import json, sys, time
import httpx

OV, mode = "http://ov:1933", sys.argv[1]
c = httpx.Client(timeout=120)
fails = 0


def call(name, method, path, headers, **kw):
    global fails
    r = c.request(method, OV + path, headers=headers, **kw)
    ok = 200 <= r.status_code < 300
    fails += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} {name}: HTTP {r.status_code} {r.text[:600]}", flush=True)
    return r


if mode == "bootstrap":
    h = {"X-API-Key": "spike-root-key-0123456789abcdef0123456789"}
    call("admin create account lab/jasper", "POST", "/api/v1/admin/accounts", h,
         json={"account_id": "lab", "admin_user_id": "jasper"})
    call("admin list accounts", "GET", "/api/v1/admin/accounts", h)
    sys.exit(1 if fails else 0)

tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
h = {"Authorization": "Bearer " + tok}
call("health with token", "GET", "/health", h)
call("ls viking://", "GET", "/api/v1/fs/ls", h, params={"uri": "viking://"})
call("ls viking://resources", "GET", "/api/v1/fs/ls", h, params={"uri": "viking://resources"})
call("mkdir viking://resources/spike", "POST", "/api/v1/fs/mkdir", h, json={"uri": "viking://resources/spike"})
call("write viking://resources/spike/note.md", "POST", "/api/v1/content/write", h,
     json={"uri": "viking://resources/spike/note.md", "content": "# Spike\nfresh bucket bootstrap probe\n",
           "mode": "create", "wait": True, "timeout": 120})
call("read it back", "GET", "/api/v1/content/read", h, params={"uri": "viking://resources/spike/note.md"})
call("find", "POST", "/api/v1/search/find", h, json={"query": "bootstrap probe", "limit": 5})
call("search", "POST", "/api/v1/search/search", h, json={"query": "bootstrap probe", "limit": 5})
r = c.get(OV + "/api/v1/fs/ls", headers=h, params={"uri": "viking://user/jasper/memories"})
print(f"INFO ls viking://user/jasper/memories (not counted): HTTP {r.status_code} {r.text[:300]}", flush=True)
call("ls viking:// after", "GET", "/api/v1/fs/ls", h, params={"uri": "viking://", "recursive": True})
sys.exit(1 if fails else 0)
