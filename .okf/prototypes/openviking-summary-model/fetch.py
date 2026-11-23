import json, pathlib, sys, urllib.parse, urllib.request
B = "https://openviking-api.lab.orangecluster.nl/api/v1"
TOK = pathlib.Path(sys.argv[1]).read_text().strip()
R = "viking://user/jasper/resources/"
DIRS = ["blogs/anthropic/coordinated-vulnerability-disclosure-timelines",
        "clips/5-non-transformer-architectures-that-beat-transformers-in-20",
        "clips/slate-moving-beyond-react-and-rlm/Slates_Approach_Thread_Weaving_and_Episodes",
        "projects/dlx",
        "handoffs/local/jasperginn"]
def get(path, **p):
    req = urllib.request.Request(f"{B}{path}?{urllib.parse.urlencode(p)}", headers={"Authorization": f"Bearer {TOK}"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60)).get("result")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
out = []
for d in DIRS:
    uri = R + d
    ls = get("/fs/ls", uri=uri, output="original")
    files = [e["uri"] for e in ls if e["uri"].endswith(".md") and not e["uri"].rsplit("/",1)[1].startswith(".")]
    item = {"dir": uri, "L1": get("/content/overview", uri=uri), "L0": get("/content/abstract", uri=uri), "files": []}
    for f in files:
        item["files"].append({"name": f.rsplit("/",1)[1], "L2": get("/content/read", uri=f), "file_abstract": get("/content/abstract", uri=f)})
    out.append(item)
    print(d, len(files), "files;", "L1", len(str(item["L1"])), "L0", len(str(item["L0"])), [ (len(str(x["L2"])), str(x["file_abstract"])[:60]) for x in item["files"]])
pathlib.Path("data.json").write_text(json.dumps(out, indent=1))
