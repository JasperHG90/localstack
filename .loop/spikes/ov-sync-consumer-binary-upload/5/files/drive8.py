"""Risk 1 of ov-sync-consumer-binary-upload, follow-up to spike 3, as lab/jasper
(USER via OIDC). D = viking://user/jasper/resources/projects/y/docs/img on a fresh
tree: nothing was ever written under projects/y. Temp folder name is fixed,
T = D/.ovsync-upload-diagram.png.
  1 round one (D and its parents missing): temp_upload a.png; add to=T
    source_name=diagram.png wait=true (no create_parent); mv T/diagram.png ->
    D/diagram.png; rm -r T. D/diagram.png downloads byte-exact a.png, ls D shows
    diagram.png plus summaries only, T gone.
  2 round two (same T name, T absent after round one's cleanup): same with
    b.png. mv overwrites D/diagram.png; byte-exact b.png; ls D clean.
  3 round three (T left over): round two's route again with c.png but skip
    the rm, so T stays holding only its summaries; then add c.png to=T, mv,
    rm -r T. Add into the existing T works, mv overwrites, byte-exact c.png,
    ls D clean, T gone.
If round one's add fails, it is retried with create_parent=true and the
check fails (the route then needs that flag); the response is printed.
Diagnostics (spike 4 found T still listed in ls D after rm -r returned 200):
after each rm, stat and ls T, ls D now and 10 s later, then a second rm -r.
Control: the same route in a folder that already holds notes.md (spike 3's
shape) with a random temp name, listed non-recursively.
Exit 0 only if 1 to 3 hold."""
import hashlib, sys, time
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources"
D = f"{R}/projects/y/docs/img"
T = f"{D}/.ovsync-upload-diagram.png"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
PNG = {k: open(f"/{k}.png", "rb").read() for k in "abc"}
sha = lambda b: hashlib.sha256(b).hexdigest()[:16] if b is not None else None
for k, v in PNG.items():
    print(f"{k}.png {len(v)} B sha {sha(v)}", flush=True)
short = lambda u: u.removeprefix(R)


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:600]}", flush=True)
    return r


def upload(data):
    r = show("temp_upload", c.post(OV + "/api/v1/resources/temp_upload", headers=H,
                                   files={"file": ("upload.png", data, "image/png")}))
    return r.json()["result"]["temp_file_id"]


def download(uri):
    r = c.get(OV + "/api/v1/content/download", headers=H, params={"uri": uri})
    print(f"[download {short(uri)}] HTTP {r.status_code} {len(r.content)} B sha {sha(r.content)}", flush=True)
    return r.content if r.status_code == 200 else None


def ls(uri, recursive=False):
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params={"uri": uri, "recursive": recursive,
                                                       "show_all_hidden": True})
    ok = r.status_code == 200
    names = [short(e.get("uri")) for e in (r.json().get("result") or [])] if ok else None
    print(f"[ls {short(uri)} recursive={recursive}] HTTP {r.status_code} {names if ok else r.text[:300]}",
          flush=True)
    return names


def add(data, tag, **extra):
    t = time.monotonic()
    body = {"temp_file_id": upload(data), "to": T, "source_name": "diagram.png", "wait": True,
            "timeout": 120, **extra}
    return show(f"add {tag} to={short(T)} {extra} in {time.monotonic() - t:.1f}s",
                c.post(OV + "/api/v1/resources", headers=H, json=body))


def mv(src, dst):
    t = time.monotonic()
    return show(f"mv {short(src)} -> {short(dst)} in {time.monotonic() - t:.2f}s",
                c.post(OV + "/api/v1/fs/mv", headers=H, json={"from_uri": src, "to_uri": dst}))


def stat(uri):
    return show(f"stat {short(uri)}", c.get(OV + "/api/v1/fs/stat", headers=H, params={"uri": uri}))


def rm_diag(uri):
    rr = rm1(uri)
    stat(uri); ls(uri); parent = uri.rsplit("/", 1)[0]; ls(parent)
    time.sleep(10)
    print("INFO 10 s after rm:", flush=True)
    ls(parent)
    rm1(uri)
    stat(uri); ls(parent)
    return rr


def rm(uri):
    return rm_diag(uri)


def rm1(uri):
    return show(f"rm -r {short(uri)}", c.delete(OV + "/api/v1/fs", headers=H, params={
        "uri": uri, "recursive": True, "wait": True, "timeout": 120}))


def d_clean(d=D):
    names = ls(d)
    if names is None:
        return False
    base = [n.rstrip("/").rsplit("/", 1)[-1] for n in names]
    return "diagram.png" in base and all(b in ("diagram.png", ".abstract.md", ".overview.md") for b in base)


def settle():
    time.sleep(6)


print("== before: does anything exist under projects/?", flush=True)
ls(f"{R}/projects")
ls(D)

print("== round one: D and parents missing", flush=True)
r = add(PNG["a"], "round1")
add_ok = r.status_code == 200 and (r.json().get("status") in (None, "ok"))
if not add_ok:
    print("INFO round one add failed; retrying with create_parent=true", flush=True)
    add(PNG["a"], "round1-retry", create_parent=True)
ls(f"{R}/projects", recursive=True)
r = mv(f"{T}/diagram.png", f"{D}/diagram.png")
settle()
print("INFO left in T after mv:", flush=True)
ls(T)
rr = rm(T)
settle()
c1 = (add_ok and r.status_code == 200 and rr.status_code == 200 and download(f"{D}/diagram.png") == PNG["a"]
      and d_clean())
print(f"CHECK 1 fresh D, no create_parent: add ok {add_ok}, D/diagram.png exact a.png, ls D clean, "
      f"T gone: {c1}", flush=True)

print("== round two: same T name after clean delete", flush=True)
r0 = add(PNG["b"], "round2")
r = mv(f"{T}/diagram.png", f"{D}/diagram.png")
settle()
rr = rm(T)
settle()
c2 = (r0.status_code == 200 and r.status_code == 200 and rr.status_code == 200
      and download(f"{D}/diagram.png") == PNG["b"] and d_clean())
print(f"CHECK 2 same T name again: D/diagram.png exact b.png, ls D clean, T gone: {c2}", flush=True)

print("== round three: T left over holding its summaries", flush=True)
r0 = add(PNG["a"], "round3-prep")
r1 = mv(f"{T}/diagram.png", f"{D}/diagram.png")
settle()
left = ls(T)
print(f"INFO leftover T before round three add: {left}", flush=True)
r2 = add(PNG["c"], "round3")
ls(T)
r = mv(f"{T}/diagram.png", f"{D}/diagram.png")
settle()
rr = rm(T)
settle()
c3 = (r0.status_code == 200 and r1.status_code == 200 and left is not None and r2.status_code == 200
      and r.status_code == 200 and rr.status_code == 200 and download(f"{D}/diagram.png") == PNG["c"]
      and d_clean())
print(f"CHECK 3 add into leftover T: D/diagram.png exact c.png, ls D clean, T gone: {c3}", flush=True)
ls(f"{R}/projects", recursive=True)

print("== control: folder with notes.md, random temp name", flush=True)
D2 = f"{R}/projects/x/ref"
show("write notes.md", c.post(OV + "/api/v1/content/write", headers=H,
     json={"uri": f"{D2}/notes.md", "content": "# notes\n", "wait": True, "timeout": 120}))
settle()
T2 = f"{D2}/.ovsync-upload-3f9a1c"
show("add control", c.post(OV + "/api/v1/resources", headers=H, json={
    "temp_file_id": upload(PNG["a"]), "to": T2, "source_name": "diagram.png", "wait": True, "timeout": 120}))
mv(f"{T2}/diagram.png", f"{D2}/diagram.png")
settle()
rm(T2)
settle()
print(f"INFO control ls D2 non-recursive / recursive:", flush=True)
ls(D2); ls(D2, recursive=True)

passed = c1 and c2 and c3
print("OVERALL", "PASS" if passed else "FAIL", flush=True)
sys.exit(0 if passed else 1)
