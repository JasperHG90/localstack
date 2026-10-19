# Runs inside the OpenViking image. "build" writes a tree with empty and
# nested directories through AGFS s3fs and saves what stat/ls/tree/glob/read
# return. "check" reads the same views from a restored bucket, compares them
# with the saved ones, then runs VikingFS.mv (stat, cp -r, rm -r) on old paths.
import json, sys
from openviking_cli.utils.config.agfs_config import AGFSConfig
from openviking.utils.agfs_utils import RagfsBindingConfig, create_agfs_client
from openviking.pyagfs.helpers import cp
mode, ep, bucket, ak, sk, path = sys.argv[1:7]
c = create_agfs_client(RagfsBindingConfig(agfs=AGFSConfig(backend="s3", path="/tmp/ovdata", s3={
    "bucket": bucket, "endpoint": ep, "region": "us-east-1", "access_key": ak,
    "secret_key": sk, "use_ssl": False, "use_path_style": True})))
R = "/local/viking/default/resources/spk"
DIRS = [R, R + "/empty1", R + "/nested", R + "/nested/b", R + "/nested/b/deeper",
        R + "/nested/empty2", R + "/docs", R + "/docs/sub"]
FILES = {R + "/a.md": b"top", R + "/nested/b/c.md": b"deep", R + "/docs/d.md": b"doc"}
def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in sorted(x.items()) if not any(t in k.lower() for t in ("time", "mod"))}
    if isinstance(x, (list, tuple)):
        return sorted((norm(v) for v in x), key=json.dumps)
    if isinstance(x, (bytes, bytearray, memoryview)):
        return bytes(x).decode(errors="replace")
    return x
def view(label, fn):
    try:
        return norm(fn())
    except Exception as e:
        return f"ERR {type(e).__name__}"
def snapshot():
    s = {}
    for d in DIRS:
        s["stat " + d] = view("stat", lambda d=d: c.stat(d))
        s["ls " + d] = view("ls", lambda d=d: [e.get("name") for e in c.ls(d)])
    for f in FILES:
        s["stat " + f] = view("stat", lambda f=f: c.stat(f))
        s["read " + f] = view("read", lambda f=f: c.read(f))
    s["tree"] = view("tree", lambda: c.tree_directory(R))
    s["glob"] = view("glob", lambda: c.glob_directory(R, "*.md"))
    return s
if mode == "build":
    c.mkdir(R); c.mkdir(R + "/empty1")
    c.ensure_parent_dirs(R + "/nested/b/c.md"); c.mkdir(R + "/nested/b/deeper")
    c.mkdir(R + "/nested/empty2"); c.mkdir(R + "/docs"); c.mkdir(R + "/docs/sub")
    for f, b in FILES.items():
        c.write(f, b)
    s = snapshot()
    errs = [k for k, v in s.items() if isinstance(v, str) and v.startswith("ERR")]
    json.dump(s, open(path, "w"), indent=1, sort_keys=True)
    print(f"built tree on {bucket}: {len(s)} views, errors on source: {errs or 'none'}")
    sys.exit(1 if errs else 0)
base = json.load(open(path)); s = snapshot(); bad = 0
for k in base:
    if base[k] != s.get(k):
        bad += 1; print(f"  DIFF {k}\n    source:   {json.dumps(base[k])[:200]}\n    restored: {json.dumps(s.get(k))[:200]}")
print(f"  {bucket}: {len(base) - bad}/{len(base)} views match the source")
def step(label, fn):
    global bad
    try:
        fn(); print(f"  PASS {label}")
    except Exception as e:
        bad += 1; print(f"  FAIL {label}: {type(e).__name__}: {e}")
step("mv: stat /nested", lambda: c.stat(R + "/nested")["isDir"] or (_ for _ in ()).throw(AssertionError("not a dir")))
step("mv: cp -r /nested /moved", lambda: cp(c, R + "/nested", R + "/moved", recursive=True))
step("mv: rm -r /nested", lambda: c.rm(R + "/nested", recursive=True))
step("after mv: read moved/b/c.md", lambda: bytes(c.read(R + "/moved/b/c.md")) == b"deep" or (_ for _ in ()).throw(AssertionError("content")))
step("after mv: stat moved/empty2 is dir", lambda: c.stat(R + "/moved/empty2")["isDir"] or (_ for _ in ()).throw(AssertionError("not a dir")))
step("after mv: stat moved/b/deeper is dir", lambda: c.stat(R + "/moved/b/deeper")["isDir"] or (_ for _ in ()).throw(AssertionError("not a dir")))
step("mv of empty dir: cp -r /empty1 /empty1mv", lambda: cp(c, R + "/empty1", R + "/empty1mv", recursive=True))
print(f"  RESULT {bucket}: {'ok' if bad == 0 else f'{bad} failures'}")
sys.exit(1 if bad else 0)
