"""Follow-up to spike:ov-sync-consumer/3, as lab/jasper (USER via OIDC):
  B  content/batch-write with root_uri = the existing resources root and
     operations under missing folders projects/bw/docs/a/b.md
  A  write projects/w/docs/a/b.md, rm it (wait), rm a/ recursive (wait),
     then watch stat of a/ and ls of docs/ at 0, 5, 20 s: does a/ come back?
  T  write projects/t/docs/a/b.md, rm it (wait), rm the top emptied folder
     t/ recursive (wait), and watch t/ the same way
Exit 0 only if the folder removed in A stays gone for 20 s."""
import sys, time
import httpx

OV = "http://ov:1933"
ROOT = "viking://user/jasper/resources"
R = ROOT + "/projects"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:400]}", flush=True)
    return r


def ok(r):
    return r.status_code == 200 and r.json().get("status") == "ok"


def stat(uri):
    r = c.get(OV + "/api/v1/fs/stat", headers=H, params={"uri": uri})
    res = r.json().get("result") or {}
    print(f"[stat {uri}] HTTP {r.status_code} count={res.get('count')}", flush=True)
    return r.status_code


def read(uri):
    r = c.get(OV + "/api/v1/content/read", headers=H, params={"uri": uri})
    return r.json().get("result") if r.status_code == 200 else None


def ls(uri):
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params={"uri": uri, "recursive": True, "show_all_hidden": True})
    names = [e.get("uri") for e in (r.json().get("result") or [])] if r.status_code == 200 else None
    print(f"[ls {uri}] HTTP {r.status_code} {names}", flush=True)
    return names


def write(uri, txt):
    return show(f"write {uri}", c.post(OV + "/api/v1/content/write", headers=H,
                                       json={"uri": uri, "content": txt, "wait": True, "timeout": 120}))


def rm(uri, **params):
    return show(f"rm {uri} {params}", c.delete(OV + "/api/v1/fs", headers=H, params={"uri": uri, **params}))


def watch(gone_uri, parent):
    states = []
    for t in (0, 5, 15):
        time.sleep(t)
        states.append(stat(gone_uri))
        ls(parent)
    return states


# B
B1 = "# B1\n\nbatch one\n"
r = show("B batch-write root=resources", c.post(OV + "/api/v1/content/batch-write", headers=H, json={
    "root_uri": ROOT, "timeout": 120,
    "operations": [{"uri": f"{R}/bw/docs/a/b.md", "content": B1}]}))
print(f"CHECK B batch-write existing root, missing folders: {ok(r) and read(f'{R}/bw/docs/a/b.md') == B1}", flush=True)

# A
write(f"{R}/w/docs/a/b.md", "w\n")
rm(f"{R}/w/docs/a/b.md", wait=True)
ra = rm(f"{R}/w/docs/a", recursive=True, wait=True)
sa = watch(f"{R}/w/docs/a", f"{R}/w/docs")
a_gone = ok(ra) and all(s == 404 for s in sa)
print(f"CHECK A a/ removed and stays gone: {a_gone} stat codes at 0/5/20 s {sa}", flush=True)

# T
write(f"{R}/t/docs/a/b.md", "t\n")
rm(f"{R}/t/docs/a/b.md", wait=True)
rt = rm(f"{R}/t", recursive=True, wait=True)
st = watch(f"{R}/t", R)
print(f"INFO T top folder t/ removed and stays gone: {ok(rt) and all(s == 404 for s in st)} stat codes {st}", flush=True)

print("OVERALL", "PASS" if a_gone else "FAIL", flush=True)
sys.exit(0 if a_gone else 1)
