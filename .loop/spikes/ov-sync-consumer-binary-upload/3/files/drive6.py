"""Risk 1 of ov-sync-consumer-binary-upload, as lab/jasper (USER via OIDC).
Spikes 1 and 2 showed POST /api/v1/resources never stores a binary at an
exact file URI beside siblings. This run places it there in three moves:
add into a hidden temp folder, POST /api/v1/fs/mv the file to D/diagram.png,
DELETE /api/v1/fs the temp folder.
  1 round one: D holds notes.md; temp_upload a.png, add to=T1 source_name=
    diagram.png wait=true, mv T1/diagram.png -> D/diagram.png, rm -r T1.
    D/diagram.png downloads byte-exact, notes.md unchanged, T1 gone from ls.
  2 round two: same with b.png onto the existing D/diagram.png. mv over the
    file is tried first; if it fails, rm D/diagram.png then mv. A poller
    downloads D/diagram.png throughout and counts answers that are not a or b.
    D/diagram.png ends byte-exact b.png, notes.md unchanged, T2 gone.
  3 index: pgvector holds D/diagram.png exactly once and nothing under the
    temp folders after the rounds; find with target D returns D/diagram.png;
    its abstract carries the fake VLM's tag for b.png after round two.
Info: VLM image-call counts across each mv (re-describe or not), summaries
in the temp folder before the mv, and what is left in it after.
Exit 0 only if 1 to 3 hold."""
import hashlib, secrets, sys, threading, time
import httpx, psycopg

OV = "http://ov:1933"
R = "viking://user/jasper/resources/projects/x/docs"
D = f"{R}/ref"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
A, B = open("/a.png", "rb").read(), open("/b.png", "rb").read()
sha = lambda b: hashlib.sha256(b).hexdigest()[:16] if b is not None else None
print(f"a.png {len(A)} B sha {sha(A)}; b.png {len(B)} B sha {sha(B)}", flush=True)


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:500]}", flush=True)
    return r


def upload(data):
    r = show("temp_upload", c.post(OV + "/api/v1/resources/temp_upload", headers=H,
                                   files={"file": ("upload.png", data, "image/png")}))
    return r.json()["result"]["temp_file_id"]


def download(uri, quiet=False):
    r = c.get(OV + "/api/v1/content/download", headers=H, params={"uri": uri})
    if not quiet:
        print(f"[download {uri.removeprefix(R)}] HTTP {r.status_code} {len(r.content)} B "
              f"sha {sha(r.content)}", flush=True)
    return r.content if r.status_code == 200 else None


def read(uri):
    r = c.get(OV + "/api/v1/content/read", headers=H, params={"uri": uri})
    return r.json().get("result") if r.status_code == 200 else f"HTTP {r.status_code}"


def ls(uri):
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params={"uri": uri, "recursive": True, "show_all_hidden": True})
    names = [e.get("uri").removeprefix(R) for e in (r.json().get("result") or [])] if r.status_code == 200 else []
    print(f"[ls {uri.removeprefix(R)}] HTTP {r.status_code} {names if r.status_code == 200 else r.text[:300]}",
          flush=True)
    return names


def mv(src, dst):
    t = time.monotonic()
    r = c.post(OV + "/api/v1/fs/mv", headers=H, json={"from_uri": src, "to_uri": dst})
    show(f"mv {src.removeprefix(R)} -> {dst.removeprefix(R)} in {time.monotonic() - t:.2f}s", r)
    return r


def rm(uri, recursive=False):
    t = time.monotonic()
    r = c.delete(OV + "/api/v1/fs", headers=H, params={"uri": uri, "recursive": recursive, "wait": True,
                                                         "timeout": 120})
    show(f"rm {uri.removeprefix(R)} recursive={recursive} in {time.monotonic() - t:.2f}s", r)
    return r


def image_calls():
    return sum(v for k, v in httpx.get("http://fake:8080/counts").json().items() if k.startswith("chat-with-image"))


def vector_uris():
    """every row in schema ovp that mentions /ref/, keyed by its uri-like fields"""
    out = []
    with psycopg.connect("postgresql://ov:ov@pg:5432/openviking") as pg:
        tabs = [t for (t,) in pg.execute("SELECT table_name FROM information_schema.tables "
                                         "WHERE table_schema='ovp'")]
        for t in tabs:
            for (row,) in pg.execute(f'SELECT row_to_json(x) FROM ovp."{t}" x WHERE row_to_json(x)::text LIKE %s',
                                     ("%/ref/%",)):
                keep = {k: v.removeprefix(R).removeprefix(R.removeprefix("viking:/"))
                        for k, v in row.items() if isinstance(v, str) and len(v) < 400
                        and ("/ref" in v or str(row.get("uri", "")).endswith("diagram.png"))}
                out.append((t, keep))
    print(f"[pgvector tables {tabs}] rows mentioning /ref/:", flush=True)
    for t, k in out:
        print(f"  {t} {k}", flush=True)
    return out


def file_abstract(rows):
    return next((k.get("abstract") for _, k in rows if k.get("uri") == "/ref/diagram.png"), None)


def find():
    r = c.post(OV + "/api/v1/search/find", headers=H, json={"query": "diagram summary content", "target_uri": D,
                                                             "limit": 50})
    res = r.json().get("result") or {}
    hits = [x for k in ("resources", "memories", "skills") for x in res.get(k) or []]
    uris = [x.get("uri", "").removeprefix(R) for x in hits]
    for x in hits:
        if x.get("uri", "").endswith("diagram.png"):
            print(f"  [find hit diagram.png] score {x.get('score')} abstract {x.get('abstract')!r:.200}", flush=True)
    print(f"[find target=/ref] HTTP {r.status_code} {uris if r.status_code == 200 else r.text[:300]}", flush=True)
    return uris


def stage(data, tag):
    """add into a fresh hidden temp folder; return (temp folder, file uri there)"""
    T = f"{D}/.ovsync-upload-{secrets.token_hex(6)}"
    t = time.monotonic()
    r = c.post(OV + "/api/v1/resources", headers=H, json={"temp_file_id": upload(data), "to": T,
                                                          "source_name": "diagram.png", "wait": True, "timeout": 120})
    show(f"add {tag} to={T.removeprefix(R)} in {time.monotonic() - t:.1f}s", r)
    names = ls(T)
    for n in names:
        if n.rsplit("/", 1)[-1].startswith("."):
            print(f"  [{n}] {read(R + n)!r:.300}", flush=True)
    return T, f"{T}/diagram.png"


def settle():
    time.sleep(6)


NOTE = "# notes\n\nbeside the diagram\n"
show("write notes.md", c.post(OV + "/api/v1/content/write", headers=H,
                              json={"uri": f"{D}/notes.md", "content": NOTE, "wait": True, "timeout": 120}))
settle()

# round one
T1, F1 = stage(A, "round1")
staged_ok = download(F1) == A
n0 = image_calls()
r = mv(F1, f"{D}/diagram.png")
settle()
print(f"INFO image VLM calls across mv round1: {n0} -> {image_calls()}", flush=True)
print("INFO left in T1 after mv:", flush=True)
ls(T1)
rm(T1, recursive=True)
settle()
after1 = ls(D)
c1 = (staged_ok and r.status_code == 200 and download(f"{D}/diagram.png") == A and read(f"{D}/notes.md") == NOTE
      and not any(".ovsync-upload" in n for n in after1))
print(f"CHECK 1 round one: D/diagram.png exact, notes.md kept, T1 gone: {c1}", flush=True)
abs1 = file_abstract(vector_uris())
find()
print(f"INFO D/.abstract.md {read(D + '/.abstract.md')!r:.300}", flush=True)

# round two, with a poller watching D/diagram.png
T2, F2 = stage(B, "round2")
seen, stop = [], threading.Event()


def poll():
    pc = httpx.Client(timeout=30)
    while not stop.is_set():
        rr = pc.get(OV + "/api/v1/content/download", headers=H, params={"uri": f"{D}/diagram.png"})
        seen.append("a" if rr.content == A else "b" if rr.content == B else f"HTTP {rr.status_code}")


th = threading.Thread(target=poll)
th.start()
time.sleep(0.5)
n0 = image_calls()
r = mv(F2, f"{D}/diagram.png")
route = "mv over existing"
if r.status_code != 200:
    route = "rm then mv"
    rm(f"{D}/diagram.png")
    r = mv(F2, f"{D}/diagram.png")
time.sleep(0.5)
stop.set()
th.join()
gaps = [s for s in seen if s not in ("a", "b")]
print(f"INFO route that worked: {route}; poller saw {len(seen)} downloads, sequence "
      f"{''.join(s if s in 'ab' else 'X' for s in seen)}; not a/b: {sorted(set(gaps))} x{len(gaps)}", flush=True)
settle()
print(f"INFO image VLM calls across mv round2: {n0} -> {image_calls()}", flush=True)
print("INFO left in T2 after mv:", flush=True)
ls(T2)
rm(T2, recursive=True)
settle()
after2 = ls(D)
c2 = (r.status_code == 200 and download(f"{D}/diagram.png") == B and read(f"{D}/notes.md") == NOTE
      and not any(".ovsync-upload" in n for n in after2))
print(f"CHECK 2 round two: D/diagram.png now exact b.png, notes.md kept, T2 gone: {c2}", flush=True)

vu = vector_uris()
fu = find()
file_rows = [k for _, k in vu if "/ref/diagram.png" in k.values()]
c3 = (len(file_rows) == 1 and not any(".ovsync-upload" in v for _, k in vu for v in k.values())
      and "/ref/diagram.png" in fu)
abs2 = file_abstract(vu)
c3b = bool(abs1 and abs2 and abs1.split()[4:5] != abs2.split()[4:5])
print(f"INFO file row abstract tag round1 {abs1 and abs1.split()[4:5]} round2 {abs2 and abs2.split()[4:5]}", flush=True)
c3 = c3 and c3b
print(f"CHECK 3 index: D/diagram.png indexed once, no temp uris, find returns it, its row describes"
      f" the new image: {c3}", flush=True)
print(f"INFO D/.abstract.md {read(D + '/.abstract.md')!r:.300}", flush=True)
print(f"INFO D/.overview.md {read(D + '/.overview.md')!r:.400}", flush=True)

passed = c1 and c2 and c3
print("OVERALL", "PASS" if passed else "FAIL", flush=True)
sys.exit(0 if passed else 1)
