"""Drive OpenViking as lab/jasper (USER role via OIDC) for the image carry-over spike.
ingest NAME DIR W [MD]: temp_upload a WxW NAME.png and add_resource it to clips/DIR,
then write MD beside it.  readd NAME DIR W: the same upload and add_resource again.  vec URI: vectors_only reindex.  sem URI REC: semantic_and_vectors reindex,
recursive REC (true/false).  find QUERY WANT: exit 0 only if find returns WANT.
Prints RESULT <json> for reindex calls."""
import json, struct, sys, time, zlib
import httpx

OV, mode = "http://ov:1933", sys.argv[1]
RES = "viking://user/jasper/resources"
c = httpx.Client(timeout=600)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
h = {"Authorization": "Bearer " + tok}


def req(method, path, **kw):
    r = c.request(method, OV + path, headers=h, **kw)
    shown = kw.get("json") or kw.get("params") or kw.get("data")
    print(f"{method} {path} {json.dumps(shown)[:200]} -> HTTP {r.status_code} {r.text[:1500]}", flush=True)
    return r


def png(w=32, hgt=32):
    raw = b"".join(b"\x00" + bytes(v for x in range(w) for v in (x * 7 % 256, y * 5 % 256, 128))
                   for y in range(hgt))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, hgt, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


ok = True
if mode in ("ingest", "readd"):
    name, d, w = sys.argv[2], sys.argv[3], int(sys.argv[4])
    r = req("POST", "/api/v1/resources/temp_upload", files={"file": (f"{name}.png", png(w, w), "image/png")})
    tid = (r.json().get("result") or {}).get("temp_file_id") or r.json().get("temp_file_id")
    r = req("POST", "/api/v1/resources", json={"temp_file_id": tid, "to": f"{RES}/clips/{d}", "create_parent": True,
                                               "reason": "spike", "wait": True, "timeout": 300})
    ok &= r.status_code == 200
    time.sleep(5)
    if mode == "ingest" and len(sys.argv) > 5:
        r = req("POST", "/api/v1/content/write",
                json={"uri": f"{RES}/clips/{d}/{sys.argv[5]}",
                      "content": "# Notes on tide tables\n\nNotes on tide tables and harbour charts.\n",
                      "mode": "create", "wait": True, "timeout": 240})
        ok &= r.status_code == 200
        time.sleep(10)
    req("GET", "/api/v1/fs/ls", params={"uri": f"{RES}/clips/{d}", "show_all_hidden": True})
elif mode in ("sem", "vec"):
    body = {"uri": sys.argv[2], "mode": "semantic_and_vectors" if mode == "sem" else "vectors_only", "wait": True}
    if mode == "sem":
        body["recursive"] = sys.argv[3] == "true"
    r = req("POST", "/api/v1/content/reindex", json=body)
    res = r.json().get("result") or {}
    print("RESULT", json.dumps({k: res.get(k) for k in ("status", "scanned_records", "rebuilt_records",
                                                        "unsupported_records", "failed_records", "warnings")}))
    ok = r.status_code == 200 and not res.get("failed_records") and res.get("status", "completed") != "failed"
elif mode == "find":
    q, want = sys.argv[2], sys.argv[3]
    r = req("POST", "/api/v1/search/find", json={"query": q, "limit": 5})
    def uris(o):
        if isinstance(o, dict):
            if isinstance(o.get("uri"), str):
                yield o["uri"]
            for v in o.values():
                yield from uris(v)
        elif isinstance(o, list):
            for v in o:
                yield from uris(v)
    got = [u for u in uris(r.json())]
    ok = any(u.endswith(want) for u in got)  # the hit must be the file itself, not a dir naming it
    print(("PASS" if ok else "FAIL"), "find", repr(q), "->", want, flush=True)
sys.exit(0 if ok else 1)
