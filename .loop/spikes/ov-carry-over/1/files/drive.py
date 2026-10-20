"""Drive OpenViking as lab/jasper (USER role via OIDC). Modes:
write: write a small tree under viking://user/jasper/resources/carry and wait.
reindex: vectors_only reindex of that tree; print the result; exit 1 on failures.
find: find each file's title; exit 1 if a file is missing from its own hits."""
import json, sys, time
import httpx

OV, mode = "http://ov:1933", sys.argv[1]
ROOT = "viking://user/jasper/resources/carry"
FILES = {
    "astronomy/comet-tails.md": ("Why comet tails point away from the sun",
                                 "Solar wind and radiation pressure push dust and ions outward."),
    "astronomy/red-dwarfs.md": ("Red dwarf stars live for trillions of years",
                                "Slow fusion in small convective stars burns hydrogen evenly."),
    "cooking/sourdough-starter.md": ("Keeping a sourdough starter alive",
                                     "Feed flour and water daily; lactobacilli and wild yeast ferment."),
    "cooking/notes/knife-sharpening.md": ("Sharpening a chef knife on whetstones",
                                          "Hold a fifteen degree angle and raise a burr before honing."),
    "gardening-tomato-blight.md": ("Tomato blight prevention in wet summers",
                                   "Mulch, prune lower leaves and water at the base early."),
}
c = httpx.Client(timeout=300)
tok = httpx.get("http://fake:8000/mint", params={"ov_account": "lab", "ov_user": "jasper"}).json()["token"]
h = {"Authorization": "Bearer " + tok}


def req(method, path, **kw):
    r = c.request(method, OV + path, headers=h, **kw)
    print(f"{method} {path} {json.dumps(kw.get('json') or kw.get('params'))[:160]} -> HTTP {r.status_code} {r.text[:1500]}",
          flush=True)
    return r


ok = True
if mode == "write":
    print("health:", req("GET", "/health").status_code)
    for rel, (title, body) in FILES.items():
        r = req("POST", "/api/v1/content/write",
                json={"uri": f"{ROOT}/{rel}", "content": f"# {title}\n\n{body}\n", "mode": "create",
                      "wait": True, "timeout": 240})
        ok &= r.status_code == 200
    time.sleep(20)
    req("GET", "/api/v1/fs/ls", params={"uri": ROOT, "recursive": True, "show_all_hidden": True})
elif mode == "reindex":
    r = req("POST", "/api/v1/content/reindex", json={"uri": ROOT, "mode": "vectors_only", "wait": True})
    res = r.json().get("result") or {}
    print("RESULT", json.dumps(res))
    ok = r.status_code == 200 and not res.get("failed_records") and res.get("status", "completed") != "failed"
elif mode == "find":
    for rel, (title, _) in FILES.items():
        want = f"{ROOT}/{rel}"
        r = req("POST", "/api/v1/search/find", json={"query": title, "limit": 5})
        uris = json.dumps(r.json())
        hit = want in uris
        print(("PASS" if hit else "FAIL"), "find", title, "->", want, flush=True)
        ok &= hit
sys.exit(0 if ok else 1)
