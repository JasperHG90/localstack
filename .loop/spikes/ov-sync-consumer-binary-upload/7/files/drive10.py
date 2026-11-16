"""ov-sync-consumer-binary-upload risk 1 follow-up, as lab/jasper (USER via OIDC).
Main (exit code): D holds notes.md and plain.png (content/write). add a.png
to=D/diagram.png; DELETE D/diagram.png/diagram.png wait; DELETE D/diagram.png
recursive wait. (1) ls D/diagram.png (consumer params) is [] and download of
the file is 404. (2) add b.png to=D/diagram.png again: download of
D/diagram.png/diagram.png matches b.png sha256, ls D/diagram.png holds only
diagram.png, ls D has no *_1* entry.
Facts (recorded only): (3) non-recursive DELETE D3/diagram.png wait=true while it
holds the live image; (4) isDir of D/diagram.png and D/plain.png in ls D."""
import hashlib, sys
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
A = open("/a.png", "rb").read()
B = open("/b.png", "rb").read()
sha = lambda b: hashlib.sha256(b).hexdigest()
short = lambda u: (u or "").removeprefix(R)
print(f"a.png {len(A)} B sha {sha(A)}\nb.png {len(B)} B sha {sha(B)}", flush=True)


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:600]}", flush=True)
    return r


def ls(uri):
    p = {"uri": uri, "show_all_hidden": "true", "node_limit": "1000", "offset": "0"}
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params=p)
    try:
        res = r.json().get("result")
    except Exception:
        res = None
    if r.status_code == 200 and isinstance(res, list):
        names = [(short(e.get("uri")), {k: e.get(k) for k in ("isDir", "is_dir", "size") if k in e}) for e in res]
        print(f"[ls {short(uri)}] HTTP 200 {names}", flush=True)
        return r.status_code, res
    print(f"[ls {short(uri)}] HTTP {r.status_code} {r.text[:300]}", flush=True)
    return r.status_code, None


def isdir_report(tag, d):
    _, res = ls(d)
    for e in res or []:
        u = short(e.get("uri")).rstrip("/")
        if u.endswith("/diagram.png") or u.endswith("/plain.png"):
            print(f"  FACT4 [{tag}] {u}: isDir={e.get('isDir', e.get('is_dir'))}", flush=True)
    return res


def download(uri):
    r = c.get(OV + "/api/v1/content/download", headers=H, params={"uri": uri})
    print(f"[download {short(uri)}] HTTP {r.status_code} {len(r.content)} B "
          f"{'sha ' + sha(r.content) if r.status_code == 200 else r.text[:200]}", flush=True)
    return r


def add(d, data):
    r = show("temp_upload", c.post(OV + "/api/v1/resources/temp_upload", headers=H,
                                   files={"file": ("upload.png", data, "image/png")}))
    tid = r.json()["result"]["temp_file_id"]
    return show(f"add to={short(d)}/diagram.png", c.post(OV + "/api/v1/resources", headers=H, json={
        "temp_file_id": tid, "to": f"{d}/diagram.png", "source_name": "diagram.png", "wait": True, "timeout": 120}))


def delete(uri, recursive):
    p = {"uri": uri, "wait": "true"}
    if recursive:
        p["recursive"] = "true"
    return show(f"DELETE {short(uri)} recursive={recursive}", c.delete(OV + "/api/v1/fs", headers=H, params=p))


def write(uri, text):
    show(f"write {short(uri)}", c.post(OV + "/api/v1/content/write", headers=H,
         json={"uri": uri, "content": text, "wait": True, "timeout": 120}))


D = f"{R}/projects/m/docs"
F = f"{D}/diagram.png/diagram.png"
print(f"== main: D={short(D)}", flush=True)
write(f"{D}/notes.md", "# notes\n")
write(f"{D}/plain.png", "not really a png\n")
add(D, A)
isdir_report("live image folder", D)
ls(f"{D}/diagram.png")
download(F)
delete(F, False)
delete(f"{D}/diagram.png", True)
print("-- after deletes", flush=True)
isdir_report("ghost empty folder", D)
st, res = ls(f"{D}/diagram.png")
dl = download(F)
check1 = st == 200 and res == [] and dl.status_code == 404
print(f"CHECK1 ls D/diagram.png empty ({st}, {res}) and download 404 ({dl.status_code}): {check1}", flush=True)
add(D, B)
print("-- after re-add", flush=True)
_, top = ls(D)
_, inner = ls(f"{D}/diagram.png")
dl = download(F)
same = dl.status_code == 200 and sha(dl.content) == sha(B)
top_names = [short(e.get("uri")).rstrip("/").rsplit("/", 1)[-1] for e in (top or [])]
inner_names = [short(e.get("uri")).rstrip("/").rsplit("/", 1)[-1] for e in (inner or [])]
no_dup = top is not None and inner is not None and not any("_1" in n for n in top_names + inner_names) \
    and inner_names == ["diagram.png"]
print(f"CHECK2 bytes match b.png: {same}; ls D names {top_names}; ls D/diagram.png names {inner_names}; "
      f"no _1 and only diagram.png inside: {no_dup}", flush=True)
isdir_report("live image folder after re-add", D)

D3 = f"{R}/projects/n/docs"
print(f"== fact 3: non-recursive DELETE of folder holding live image, D3={short(D3)}", flush=True)
write(f"{D3}/notes.md", "# notes\n")
add(D3, A)
ls(D3); ls(f"{D3}/diagram.png")
delete(f"{D3}/diagram.png", False)
print("-- after non-recursive DELETE", flush=True)
ls(D3); ls(f"{D3}/diagram.png")
r = download(f"{D3}/diagram.png/diagram.png")
print(f"  FACT3 image survives: {r.status_code == 200 and sha(r.content) == sha(A)}", flush=True)

ok = check1 and same and no_dup
print(f"OVERALL check1 {check1} check2 {same and no_dup}", flush=True)
sys.exit(0 if ok else 1)
