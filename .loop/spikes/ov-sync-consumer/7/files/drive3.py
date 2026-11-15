"""Risk 1 of ov-sync-consumer, judged on OpenViking's own listing, as lab/jasper
(USER via OIDC) on a fresh instance where resources/projects/ does not exist:
  1 content/write projects/x/docs/a/b.md (no parents exist), exact read-back
  2 DELETE /api/v1/fs the file (wait): 200, read then fails
  3 DELETE the emptied a/ non-recursive (expect 412: OpenViking left its
    .abstract.md/.overview.md there) then recursive=true: 200
  4 ls of docs/ does not list a/ or anything under it at 0, 5 and 20 s
  5 content/write the same path again: 200, exact read-back, ls lists it
  6 info: content/batch-write with root_uri an existing folder (x/docs)
    and an operation under missing folders below it
Exit 0 only if 1 to 5 hold."""
import sys, time
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources/projects"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:300]}", flush=True)
    return r


def ok(r):
    return r.status_code == 200 and r.json().get("status") == "ok"


def read(uri):
    r = c.get(OV + "/api/v1/content/read", headers=H, params={"uri": uri})
    return r.json().get("result") if r.status_code == 200 else None


def ls(uri):
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params={"uri": uri, "recursive": True, "show_all_hidden": True})
    names = [e.get("uri") for e in (r.json().get("result") or [])] if r.status_code == 200 else None
    print(f"[ls {uri}] HTTP {r.status_code} {names}", flush=True)
    return names or []


def write(uri, txt):
    return show(f"write {uri}", c.post(OV + "/api/v1/content/write", headers=H,
                                       json={"uri": uri, "content": txt, "wait": True, "timeout": 120}))


def rm(uri, **params):
    return show(f"rm {uri} {params}", c.delete(OV + "/api/v1/fs", headers=H, params={"uri": uri, **params}))


docs, a, f = f"{R}/x/docs", f"{R}/x/docs/a", f"{R}/x/docs/a/b.md"
T1, T2 = "# one\n\nfirst version\n", "# two\n\nwritten again after the folder was deleted\n"
c1 = ok(write(f, T1)) and read(f) == T1
print(f"CHECK 1 write under missing folders, exact read: {c1}", flush=True)
c2 = ok(rm(f, wait=True)) and read(f) is None
print(f"CHECK 2 file delete: {c2}", flush=True)
ls(a)
nr = rm(a, wait=True).status_code
c3 = nr == 412 and ok(rm(a, recursive=True, wait=True))
print(f"CHECK 3 emptied folder: non-recursive HTTP {nr}, recursive ok: {c3}", flush=True)
c4 = True
for t in (0, 5, 15):
    time.sleep(t)
    c4 &= not any(u == a or u.startswith(a + "/") for u in ls(docs))
print(f"CHECK 4 a/ absent from ls of docs/ at 0/5/20 s: {c4}", flush=True)
c5 = ok(write(f, T2)) and read(f) == T2 and f in ls(docs)
print(f"CHECK 5 rewrite same path after folder delete: {c5}", flush=True)
r = show("6 batch-write root=x/docs", c.post(OV + "/api/v1/content/batch-write", headers=H, json={
    "root_uri": docs, "timeout": 120,
    "operations": [{"uri": f"{docs}/n/m/k.md", "content": "k\n"}]}))
print(f"INFO 6 batch-write existing folder root, missing subfolders: {ok(r) and read(f'{docs}/n/m/k.md') == 'k\n'}", flush=True)
passed = c1 and c2 and c3 and c4 and c5
print("OVERALL", "PASS" if passed else "FAIL", flush=True)
sys.exit(0 if passed else 1)
