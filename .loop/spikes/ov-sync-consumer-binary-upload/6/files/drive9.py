"""ov-sync-consumer-binary-upload: does deleting a natively stored PNG
(add to=D/diagram.png stores D/diagram.png/diagram.png) remove D/diagram.png
from ls D? As lab/jasper (USER via OIDC).
  A: D holds notes.md (content/write); add; DELETE file (wait); DELETE
     D/diagram.png recursive (wait).
  B: D missing before the add; same two DELETEs.
  C: D holds notes.md; add; DELETE D/diagram.png recursive only.
ls D with the consumer's parameters (show_all_hidden=true, node_limit=1000,
offset=0) and with output=original added, before the deletes, right after,
after 5 s and after 30 s. If still listed at 30 s: stat/download the file,
ls and stat D/diagram.png.
Exit 0 only if D/diagram.png is gone from ls D by 30 s in every case."""
import hashlib, sys, time
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
PNG = open("/a.png", "rb").read()
sha = lambda b: hashlib.sha256(b).hexdigest()[:16]
short = lambda u: (u or "").removeprefix(R)
print(f"a.png {len(PNG)} B sha {sha(PNG)}", flush=True)


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:500]}", flush=True)
    return r


def ls(uri, original=False):
    p = {"uri": uri, "show_all_hidden": "true", "node_limit": "1000", "offset": "0"}
    if original:
        p["output"] = "original"
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params=p)
    try:
        res = r.json().get("result")
    except Exception:
        res = None
    names = None
    if r.status_code == 200 and isinstance(res, list):
        names = [(short(e.get("uri")), "dir" if e.get("isDir", e.get("is_dir")) else "file") for e in res]
    print(f"[ls {short(uri)}{' output=original' if original else ''}] HTTP {r.status_code} "
          f"{names if names is not None else r.text[:300]}", flush=True)
    return names


def listed(d):
    out = []
    for orig in (False, True):
        n = ls(d, orig)
        out.append(n is not None and any(u.rstrip("/").endswith("/diagram.png") for u, _ in n))
    print(f"  -> diagram.png listed (consumer params, output=original): {out}", flush=True)
    return any(out)


def add(d):
    r = show("temp_upload", c.post(OV + "/api/v1/resources/temp_upload", headers=H,
                                   files={"file": ("upload.png", PNG, "image/png")}))
    tid = r.json()["result"]["temp_file_id"]
    return show(f"add to={short(d)}/diagram.png", c.post(OV + "/api/v1/resources", headers=H, json={
        "temp_file_id": tid, "to": f"{d}/diagram.png", "source_name": "diagram.png", "wait": True, "timeout": 120}))


def delete(uri, recursive):
    p = {"uri": uri, "wait": "true"}
    if recursive:
        p["recursive"] = "true"
    return show(f"DELETE {short(uri)} recursive={recursive}", c.delete(OV + "/api/v1/fs", headers=H, params=p))


def probe(d):
    f = f"{d}/diagram.png/diagram.png"
    show(f"stat {short(f)}", c.get(OV + "/api/v1/fs/stat", headers=H, params={"uri": f}))
    r = c.get(OV + "/api/v1/content/download", headers=H, params={"uri": f})
    print(f"[download {short(f)}] HTTP {r.status_code} {len(r.content)} B "
          f"{'sha ' + sha(r.content) if r.status_code == 200 else r.text[:200]}", flush=True)
    ls(f"{d}/diagram.png"); ls(f"{d}/diagram.png", True)
    show(f"stat {short(d)}/diagram.png", c.get(OV + "/api/v1/fs/stat", headers=H, params={"uri": f"{d}/diagram.png"}))


def case(name, d, notes, two_step):
    print(f"== case {name}: D={short(d)} notes={notes} two_step={two_step}", flush=True)
    if notes:
        show("write notes.md", c.post(OV + "/api/v1/content/write", headers=H,
             json={"uri": f"{d}/notes.md", "content": "# notes\n", "wait": True, "timeout": 120}))
    else:
        ls(d)
    add(d)
    print("-- before deletes", flush=True)
    listed(d); ls(f"{d}/diagram.png")
    if two_step:
        delete(f"{d}/diagram.png/diagram.png", False)
        print("-- after file DELETE", flush=True)
        listed(d)
    delete(f"{d}/diagram.png", True)
    t0 = time.monotonic()
    res = {}
    print("-- immediately after dir DELETE", flush=True)
    res["0s"] = listed(d)
    time.sleep(max(0, 5 - (time.monotonic() - t0)))
    print("-- 5 s after dir DELETE", flush=True)
    res["5s"] = listed(d)
    time.sleep(max(0, 30 - (time.monotonic() - t0)))
    print("-- 30 s after dir DELETE", flush=True)
    res["30s"] = listed(d)
    if res["30s"]:
        print("-- still listed at 30 s: probing", flush=True)
        probe(d)
    print(f"RESULT case {name}: listed {res}", flush=True)
    return not res["30s"]


ok_a = case("A", f"{R}/projects/a/docs", True, True)
ok_b = case("B", f"{R}/projects/b/docs/img", False, True)
ok_c = case("C", f"{R}/projects/c/docs", True, False)
print(f"OVERALL gone by 30 s: A {ok_a} B {ok_b} C {ok_c}", flush=True)
sys.exit(0 if ok_a and ok_b and ok_c else 1)
