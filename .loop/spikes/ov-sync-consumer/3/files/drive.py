"""As lab/jasper (USER via OIDC) on a fresh instance where resources/projects/
does not exist:
  W  content/write a file at projects/w/docs/a/b.md (no parents exist)
  B  content/batch-write two files under projects/bw/ (root_uri missing too)
  D  DELETE /api/v1/fs the file, then its emptied folder a/ (non-recursive
     first, recursive only if that is refused), then docs/
  N  informational: write with wait=false, delete file and folder at once
Exit 0 only if W or B creates the nested files with exact read-back, and both
the file delete and the emptied-folder delete succeed and leave nothing in ls."""
import sys, time
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources/projects"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:500]}", flush=True)
    return r


def ok(r):
    return r.status_code == 200 and r.json().get("status") == "ok"


def stat(uri):
    return show(f"stat {uri}", c.get(OV + "/api/v1/fs/stat", headers=H, params={"uri": uri})).status_code


def read(uri):
    r = c.get(OV + "/api/v1/content/read", headers=H, params={"uri": uri})
    return r.json().get("result") if r.status_code == 200 else None


def ls(uri, hidden=False):
    p = {"uri": uri, "recursive": True}
    if hidden:
        p["show_all_hidden"] = True
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params=p)
    names = [e.get("uri") for e in (r.json().get("result") or [])] if r.status_code == 200 else None
    print(f"[ls {uri} hidden={hidden}] HTTP {r.status_code} {names}", flush=True)
    return names


def rm(uri, **params):
    return show(f"rm {uri} {params}", c.delete(OV + "/api/v1/fs", headers=H, params={"uri": uri, **params}))


def rm_dir(uri):
    """Non-recursive first; recursive only if refused. Returns the params that worked."""
    r = rm(uri, wait=True)
    if ok(r):
        return "recursive=false"
    r = rm(uri, recursive=True, wait=True)
    return "recursive=true" if ok(r) else None


# W: content/write under missing parents, default mode (replace), then mode=create.
W_TXT = "# W\n\nwritten by content/write under missing folders\n"
w_uri = f"{R}/w/docs/a/b.md"
r = show("W write replace", c.post(OV + "/api/v1/content/write", headers=H,
                                   json={"uri": w_uri, "content": W_TXT, "wait": True, "timeout": 120}))
w_ok = ok(r) and read(w_uri) == W_TXT
if not ok(r):
    r = show("W write create", c.post(OV + "/api/v1/content/write", headers=H,
                                      json={"uri": w_uri, "content": W_TXT, "mode": "create", "wait": True, "timeout": 120}))
    w_ok = ok(r) and read(w_uri) == W_TXT
print(f"CHECK W content/write nested create + exact read: {w_ok}", flush=True)
ls(f"{R}/w", hidden=True)

# B: content/batch-write, root_uri itself missing.
B1, B2 = "# B1\n\nbatch one\n", "# B2\n\nbatch two\n"
r = show("B batch-write", c.post(OV + "/api/v1/content/batch-write", headers=H, json={
    "root_uri": f"{R}/bw", "timeout": 120,
    "operations": [{"uri": f"{R}/bw/docs/a/b.md", "content": B1},
                   {"uri": f"{R}/bw/docs/c/d/e.md", "content": B2, "mode": "upsert"}]}))
b_ok = ok(r) and read(f"{R}/bw/docs/a/b.md") == B1 and read(f"{R}/bw/docs/c/d/e.md") == B2
print(f"CHECK B batch-write nested create + exact read: {b_ok}", flush=True)
ls(f"{R}/bw", hidden=True)

# D: delete the file, then its emptied folder, then the next folder up.
target = w_uri if w_ok else f"{R}/bw/docs/a/b.md"
base = target.rsplit("/docs/", 1)[0]
r = rm(target, wait=True)
f_ok = ok(r) and stat(target) != 200
print(f"CHECK D file delete: {f_ok}", flush=True)
ls(f"{base}/docs/a", hidden=True)
how_a = rm_dir(f"{base}/docs/a")
a_gone = how_a is not None and stat(f"{base}/docs/a") != 200
print(f"CHECK D emptied folder a/ delete: {a_gone} via {how_a}", flush=True)
how_docs = rm_dir(f"{base}/docs")
print(f"INFO docs/ delete after a/ gone: via {how_docs}", flush=True)
left = ls(base, hidden=True)
clean = left is not None and not any("/docs" in u for u in left)
print(f"CHECK D nothing left under {base}/docs in ls: {clean}", flush=True)

# N: no wait between write and deletes (the consumer may not wait).
n_uri = f"{R}/nw/docs/a/b.md"
show("N write wait=false", c.post(OV + "/api/v1/content/write", headers=H, json={"uri": n_uri, "content": "n\n"}))
rn = rm(n_uri)
hn = rm_dir(f"{R}/nw/docs/a")
time.sleep(15)
print(f"INFO N file rm ok={ok(rn)} folder via {hn}; after 15 s:", flush=True)
ls(f"{R}/nw", hidden=True)

passed = (w_ok or b_ok) and f_ok and a_gone and clean
print("OVERALL", "PASS" if passed else "FAIL", flush=True)
sys.exit(0 if passed else 1)
