"""Risk 1 of ov-sync-consumer-binary-upload, as lab/jasper (USER via OIDC).
A trial run showed POST /api/v1/resources treats `to` as the folder that
holds the file and names the file from source_name (default: the uploaded
filename): to=<...>/ref/diagram.png stored <...>/ref/diagram.png/diagram.png.
So the exact file URI P = D/name is reached with to=D, source_name=name:
  A POST /api/v1/resources/temp_upload, multipart field "file": temp_file_id
  B D already holds notes.md (content/write). add a.png with to=D,
    source_name=diagram.png, wait=true: 200, and download of D/diagram.png
    right after the call returns is byte-exact (wait means stored)
  C add b.png to=D source_name=other.png: other.png exact, diagram.png and
    notes.md unchanged (adding beside does not replace the folder)
  D add b.png to=D source_name=diagram.png: diagram.png now equals b.png,
    other.png and notes.md unchanged (overwrite in place)
Info only: to=<exact file URI>, wait=false, and the add while the fake VLM
answers 500 to every image request.
Exit 0 only if A to D hold."""
import hashlib, sys, time
import httpx

OV = "http://ov:1933"
R = "viking://user/jasper/resources/projects/x/docs"
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
A, B = open("/a.png", "rb").read(), open("/b.png", "rb").read()
sha = lambda b: hashlib.sha256(b).hexdigest()[:16] if b is not None else None
print(f"a.png {len(A)} B sha {sha(A)}; b.png {len(B)} B sha {sha(B)}", flush=True)


def show(tag, r):
    print(f"[{tag}] HTTP {r.status_code} {r.text[:400]}", flush=True)
    return r


def upload(data, name="upload.png"):
    r = show("temp_upload", c.post(OV + "/api/v1/resources/temp_upload", headers=H,
                                   files={"file": (name, data, "image/png")}))
    return (r.json().get("result") or {}).get("temp_file_id") if r.status_code == 200 else None


def add(tid, label, **body):
    t = time.monotonic()
    r = c.post(OV + "/api/v1/resources", headers=H, json={"temp_file_id": tid, **body})
    show(f"add {label} {body} in {time.monotonic() - t:.1f}s", r)
    return r


def download(uri):
    r = c.get(OV + "/api/v1/content/download", headers=H, params={"uri": uri})
    print(f"[download {uri}] HTTP {r.status_code} {r.headers.get('content-type')} "
          f"{len(r.content)} B sha {sha(r.content)}", flush=True)
    return r.content if r.status_code == 200 else None


def read(uri):
    r = c.get(OV + "/api/v1/content/read", headers=H, params={"uri": uri})
    return r.json().get("result") if r.status_code == 200 else None


def ls(uri):
    r = c.get(OV + "/api/v1/fs/ls", headers=H, params={"uri": uri, "recursive": True, "show_all_hidden": True})
    names = [(e.get("uri").removeprefix(R), e.get("isDir"), e.get("size")) for e in (r.json().get("result") or [])] \
        if r.status_code == 200 else r.text[:300]
    print(f"[ls {uri}] HTTP {r.status_code} {names}", flush=True)


D = f"{R}/ref"
NOTE = "# notes\n\nbeside the diagram\n"
show("write notes.md", c.post(OV + "/api/v1/content/write", headers=H,
                              json={"uri": f"{D}/notes.md", "content": NOTE, "wait": True, "timeout": 120}))
tid = upload(A, "anything.png")
cA = bool(tid)
print(f"CHECK A temp_upload returns temp_file_id: {cA} ({tid})", flush=True)

r = add(tid, "B", to=D, source_name="diagram.png", wait=True, timeout=120)
cB = r.status_code == 200 and download(f"{D}/diagram.png") == A
ls(D)
print(f"CHECK B to=folder + source_name, wait=true, D/diagram.png exact right after return: {cB}", flush=True)

r = add(upload(B), "C", to=D, source_name="other.png", wait=True, timeout=120)
cC = (r.status_code == 200 and download(f"{D}/other.png") == B
      and download(f"{D}/diagram.png") == A and read(f"{D}/notes.md") == NOTE)
ls(D)
print(f"CHECK C sibling added, diagram.png and notes.md unchanged: {cC}", flush=True)

r = add(upload(B), "D", to=D, source_name="diagram.png", wait=True, timeout=120)
cD = (r.status_code == 200 and download(f"{D}/diagram.png") == B
      and download(f"{D}/other.png") == B and read(f"{D}/notes.md") == NOTE)
ls(D)
print(f"CHECK D overwrite diagram.png in place, siblings unchanged: {cD}", flush=True)

E = f"{R}/exact/diagram.png"
add(upload(A, "diagram.png"), "to=exact file URI", to=E, wait=True, timeout=120)
ls(f"{R}/exact")
print(f"INFO to=exact URI: download {E} exact: {download(E) == A}; "
      f"{E}/diagram.png exact: {download(E + '/diagram.png') == A}", flush=True)

add(upload(A), "nowait", to=D, source_name="nowait.png", wait=False)
print(f"INFO wait=false download right after return exact: {download(f'{D}/nowait.png') == A}", flush=True)
time.sleep(5)
print(f"INFO wait=false download after 5 s exact: {download(f'{D}/nowait.png') == A}", flush=True)

print(httpx.get("http://fake:8080/fail_images", params={"on": "1"}).text, flush=True)
r = add(upload(A), "vlm-fail", to=D, source_name="vlmfail.png", wait=True, timeout=120)
print(f"INFO add while VLM answers 500 on images: HTTP {r.status_code}, "
      f"download exact: {download(f'{D}/vlmfail.png') == A}", flush=True)
httpx.get("http://fake:8080/fail_images", params={"on": "0"})
print(f"[abstract of vlmfail.png folder entry] {read(f'{D}/.abstract.md')!r:.300}", flush=True)
ls(D)

passed = cA and cB and cC and cD
print("OVERALL", "PASS" if passed else "FAIL", flush=True)
sys.exit(0 if passed else 1)
