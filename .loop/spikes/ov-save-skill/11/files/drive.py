"""Save local text files the way Hermes plugin 2.1.1 _tool_add_resource does
(multipart temp_upload, then POST /api/v1/resources with source_name and
temp_file_id) as lab/jasper (USER via OIDC), into folders that do not exist.
Prints one line per case. Exit 0 only if create_parent: true creates missing
nested folders under parent=, the file lands there and find returns it, and
create_parent: true with an existing parent still saves without harm."""
import json, sys, tempfile, time
from pathlib import Path
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
TMP = Path(tempfile.mkdtemp())


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:700]}", flush=True)


def save(tag, name, title, extra):
    p = TMP / name
    p.write_text(f"# {title}\n\n{title}. Notes kept for the spike about {name}.\n")
    with p.open("rb") as f:
        u = c.post(OV + "/api/v1/resources/temp_upload", headers=H, files={"file": (p.name, f, "text/markdown")})
    tid = u.json().get("result", {}).get("temp_file_id", "")
    payload = {"reason": "spike", "wait": True, "timeout": 240, "source_name": p.name, "temp_file_id": tid, **extra}
    print(f"[{tag}] payload {json.dumps({k: v for k, v in payload.items() if k != 'temp_file_id'})}", flush=True)
    r = c.post(OV + "/api/v1/resources", headers=H, json=payload)
    show(tag, r)
    return r


def ls(uri):
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params={"uri": uri, "recursive": True})
    names = [e.get("uri") for e in (r.json().get("result") or [])] if r.status_code == 200 else []
    print(f"[ls {uri}] HTTP {r.status_code} {names}", flush=True)
    return r.status_code, names


def exists(uri):
    r = c.get(OV + "/api/v1/fs/stat", headers=H, params={"uri": uri})
    print(f"[stat {uri}] HTTP {r.status_code} {r.text[:200]}", flush=True)
    return r.status_code == 200


def find(title, want_prefix):
    for _ in range(6):
        r = c.post(OV + "/api/v1/search/find", headers=H, json={"query": title, "limit": 20})
        uris = [x.get("uri", "") for k in ("resources", "memories", "skills")
                for x in (r.json().get("result") or {}).get(k, [])]
        hit = any(u.startswith(want_prefix) for u in uris)
        if hit:
            break
        time.sleep(5)
    print(f"[find {title!r}] {'HIT' if hit else 'MISS'} want under {want_prefix} got {uris}", flush=True)
    return hit


ok = True
# (a0) missing nested parent, no create_parent: the plugin's payload today.
r = save("a0 parent missing, no create_parent", "alpha.md", "Alpha comet survey", {"parent": f"{R}/newroot/sub/"})
print("RESULT a0 no-create_parent:", "accepted" if r.status_code == 200 and r.json().get("status") == "ok" else "refused", flush=True)
exists(f"{R}/newroot")
# (a0w) same, wait false: is the refusal synchronous?
r = save("a0w parent missing, no create_parent, wait=false", "alpha2.md", "Alpha two nebula", {"parent": f"{R}/newroot/sub/", "wait": False})
# (a1) missing nested parent with create_parent: true
r = save("a1 parent missing, create_parent true", "bravo.md", "Bravo glacier retreat", {"parent": f"{R}/newroot1/sub/", "create_parent": True})
a1 = r.status_code == 200 and r.json().get("status") == "ok"
root = (r.json().get("result") or {}).get("root_uri", "") if a1 else ""
print("RESULT a1 create_parent:", "accepted" if a1 else "refused", "root_uri", root, flush=True)
d1 = exists(f"{R}/newroot1") and exists(f"{R}/newroot1/sub")
_, names = ls(f"{R}/newroot1")
under = bool(root) and root.startswith(f"{R}/newroot1/sub/")
f1 = a1 and find("Bravo glacier retreat", f"{R}/newroot1/sub/")
print(f"CHECK a1: accepted={a1} both-dirs={d1} root-under-sub={under} findable={f1}", flush=True)
ok &= a1 and d1 and under and f1
# (a2) existing parent with create_parent: true is harmless
r = save("a2 parent exists, create_parent true", "charlie.md", "Charlie tidal locking", {"parent": f"{R}/newroot1/sub/", "create_parent": True})
a2 = r.status_code == 200 and r.json().get("status") == "ok"
_, names2 = ls(f"{R}/newroot1")
kept = all(n in names2 for n in names)
f2 = a2 and find("Charlie tidal locking", f"{R}/newroot1/sub/") and find("Bravo glacier retreat", f"{R}/newroot1/sub/")
print(f"CHECK a2: accepted={a2} earlier-entries-kept={kept} both-findable={f2}", flush=True)
ok &= a2 and kept and f2
# (b0/b1) to= a full URI under a missing folder
r = save("b0 to= under missing, no create_parent", "delta.md", "Delta aurora colors", {"to": f"{R}/newroot2/sub/delta.md"})
b0 = r.status_code == 200 and r.json().get("status") == "ok"
print("RESULT b0 to= no-create_parent:", "accepted" if b0 else "refused", flush=True)
if b0:
    exists(f"{R}/newroot2/sub"); ls(f"{R}/newroot2"); find("Delta aurora colors", f"{R}/newroot2/sub/")
r = save("b1 to= under missing, create_parent true", "echo.md", "Echo pulsar timing", {"to": f"{R}/newroot3/sub/echo.md", "create_parent": True})
b1 = r.status_code == 200 and r.json().get("status") == "ok"
print("RESULT b1 to= create_parent:", "accepted" if b1 else "refused", flush=True)
if b1:
    exists(f"{R}/newroot3/sub"); ls(f"{R}/newroot3"); find("Echo pulsar timing", f"{R}/newroot3/sub/")
# (z) field name check: a near-miss name is refused (extra=forbid)
r = save("z wrong field name", "zulu.md", "Zulu wrong field", {"parent": f"{R}/newroot4/sub/", "parent_auto_create": True})
print("RESULT z parent_auto_create:", r.status_code, flush=True)
print("OVERALL", "PASS" if ok else "FAIL", flush=True)
sys.exit(0 if ok else 1)
