"""Spike ov-save-skill risk 2: a map file at viking://user/jasper/resources/.map.md.
Seeds a small tree, then as lab/jasper (USER via OIDC) creates, replaces and appends
the map, and once more replaces it with processing_mode=vectors_only. After each write
it reads the map back (GET content/read, and the Hermes plugin's viking_read path at
level=full and the default level=overview), counts stub chat (VLM) calls, lists which
storage keys under resources/ changed, counts vector rows for the map, and checks find,
search and ls for it. Exit 0 only if every write is HTTP 200, every read returns the
exact text, and no write rewrites a subdirectory's .abstract.md/.overview.md."""
import json, sys, time
import httpx, psycopg

OV, FILER, BUCKET, SCHEMA = "http://ov:1933", "http://swfs:8888", sys.argv[1], sys.argv[2]
RES = "viking://user/jasper/resources"
KEYROOT = f"/buckets/{BUCKET}/lab/user/jasper/resources"
SEED = {
    "astronomy/comet-tails.md": "# Why comet tails point away from the sun\n\nSolar wind pushes dust outward.\n",
    "astronomy/red-dwarfs.md": "# Red dwarf stars live long\n\nSlow fusion burns hydrogen evenly.\n",
    "cooking/sourdough.md": "# Keeping a sourdough starter alive\n\nFeed flour and water daily.\n",
    "cooking/knives.md": "# Sharpening a chef knife\n\nHold a fifteen degree angle.\n",
    "gardening/blight.md": "# Tomato blight in wet summers\n\nMulch and prune lower leaves.\n",
    "gardening/compost.md": "# Hot composting\n\nTurn the pile weekly.\n",
}
MAP_V1 = "# Resource map\n\n- astronomy/: space notes (zanzibarquokka)\n- cooking/: kitchen notes\n"
MAP_V2 = "# Resource map\n\n- astronomy/: comets, stars (zanzibarquokka)\n- cooking/: bread, knives\n- gardening/: blight, compost\n"
MAP_APP = "- blogs/: added later\n"
MAP_V3 = "# Resource map\n\n- astronomy/ (zanzibarquokka)\n- cooking/\n- gardening/\n- blogs/\n"

c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
c.headers["Authorization"] = "Bearer " + tok
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    if not ok:
        fails.append(name)


def req(method, path, show=600, **kw):
    r = c.request(method, OV + path, **kw)
    print(f"  {method} {path} {json.dumps(kw.get('json') or kw.get('params'))[:200]} -> HTTP {r.status_code} {r.text[:show]}",
          flush=True)
    return r


def chats():
    return sum(v for k, v in httpx.get("http://fake:8080/counts").json().items() if k.startswith("chat"))


def prompts():
    return httpx.get("http://fake:8080/prompts").json()


def snapshot():
    out = {}

    def walk(d):
        r = httpx.get(f"{FILER}{d}/", headers={"Accept": "application/json"}, params={"limit": 1000})
        for e in (r.json().get("Entries") or []):
            p = e["FullPath"]
            if e.get("Mode", 0) & 0o20000000000:
                walk(p)
            else:
                out[p[len(KEYROOT):]] = (e.get("Mtime"), e.get("Md5") or e.get("FileSize"))
    walk(KEYROOT)
    return out


def vrows(pattern):
    with psycopg.connect("postgresql://ov:ov@pg:5432/openviking") as db:
        t = db.execute("select table_name from information_schema.columns where table_schema=%s and column_name='uri' "
                       "and table_name not like '%%delta%%' limit 1", (SCHEMA,)).fetchone()[0]
        return [r[0] for r in db.execute(f'select uri from {SCHEMA}."{t}" where account_id=%s and uri like %s order by 1',
                                         ("lab", pattern)).fetchall()]


def unwrap(resp):
    return resp.get("result") if isinstance(resp, dict) and "result" in resp else resp


def plugin_read(uri, level):
    """Same calls as hermes plugin _read_uri_payload for a single non-pseudo URI."""
    used_fallback = False
    if level in {"abstract", "overview"}:
        st = unwrap(c.get(OV + "/api/v1/fs/stat", params={"uri": uri}).json())
        is_dir = bool(st.get("isDir", st.get("is_dir"))) if isinstance(st, dict) and ("isDir" in st or "is_dir" in st) else None
        used_fallback = is_dir is False
    ep = "/api/v1/content/read" if (used_fallback or level == "full") else \
        {"abstract": "/api/v1/content/abstract", "overview": "/api/v1/content/overview"}[level]
    r = c.get(OV + ep, params={"uri": uri})
    res = unwrap(r.json())
    content = res if isinstance(res, str) else (res.get("content", "") or res.get("text", "")) if isinstance(res, dict) else ""
    max_len = {"abstract": 1200, "overview": 4000}.get(level, 8000)
    return ep, r.status_code, content[:max_len]


def visibility(map_uri):
    name = map_uri.rsplit("/", 1)[1]
    rows = vrows(f"%/resources/{name}")
    print(f"  vector rows for the map: {len(rows)} {rows}")
    hits = {}
    for ep in ("/api/v1/search/find", "/api/v1/search/search"):
        r = req("POST", ep, show=300, json={"query": "zanzibarquokka resource map", "limit": 10})
        hits[ep] = map_uri in r.text
    ls = req("GET", "/api/v1/fs/ls", show=900, params={"uri": RES})
    ls_all = req("GET", "/api/v1/fs/ls", show=900, params={"uri": RES, "show_all_hidden": True})
    print(f"  VIS rows={len(rows)} find={hits['/api/v1/search/find']} search={hits['/api/v1/search/search']} "
          f"ls={name in ls.text} ls_all_hidden={name in ls_all.text}", flush=True)


def write_step(label, uri, content, mode, expect, processing_mode=None):
    c0, p0, s0 = chats(), len(prompts()), snapshot()
    time.sleep(1.5)
    body = {"uri": uri, "content": content, "mode": mode, "wait": True, "timeout": 240}
    if processing_mode:
        body["processing_mode"] = processing_mode
    r = req("POST", "/api/v1/content/write", json=body)
    time.sleep(10)
    c1, s1 = chats(), snapshot()
    ok = r.status_code == 200
    check(f"{label}: write mode={mode} HTTP 200", ok)
    changed = sorted(k for k in set(s0) | set(s1) if s0.get(k) != s1.get(k))
    print(f"  VLM {label}: {c1 - c0} chat calls; keys changed: {changed}")
    for p in prompts()[p0:]:
        print("    prompt:", p[:220].replace("\\n", " "))
    sub_sidecars = [k for k in changed if k.count("/") >= 2 and k.rsplit("/", 1)[1] in (".abstract.md", ".overview.md")]
    check(f"{label}: no subdirectory summary rewritten", not sub_sidecars, str(sub_sidecars))
    if not ok:
        return False
    r = req("GET", "/api/v1/content/read", show=300, params={"uri": uri})
    got = unwrap(r.json()) if r.status_code == 200 else None
    check(f"{label}: content/read exact", got == expect, repr(got)[:200])
    for level in ("full", "overview"):
        ep, code, txt = plugin_read(uri, level)
        check(f"{label}: plugin viking_read level={level} exact (via {ep})", code == 200 and txt == expect, repr(txt)[:200])
    visibility(uri)
    return True


print("== seed a tree under resources/")
c0 = chats()
for rel, txt in SEED.items():
    r = req("POST", "/api/v1/content/write", show=200,
            json={"uri": f"{RES}/{rel}", "content": txt, "mode": "create", "wait": True, "timeout": 240})
    if r.status_code != 200:
        print("seed failed"); sys.exit(2)
time.sleep(20)
print(f"  seed: {chats() - c0} chat calls; keys: {sorted(snapshot())}")
print(f"  vector rows under resources/: {len(vrows('/user/jasper/resources/%'))}")

for name in (".map.md", "_map.md"):
    uri = f"{RES}/{name}"
    print(f"== map name {name}")
    if not write_step("create", uri, MAP_V1, "create", MAP_V1):
        print(f"  {name} refused, trying next name")
        continue
    write_step("replace", uri, MAP_V2, "replace", MAP_V2)
    write_step("append", uri, MAP_APP, "append", MAP_V2 + MAP_APP)
    print("== extra (informational): replace with processing_mode=vectors_only")
    write_step("replace-vectors_only", uri, MAP_V3, "replace", MAP_V3, processing_mode="vectors_only")
    break
print("FAILED:", fails)
sys.exit(1 if fails else 0)
