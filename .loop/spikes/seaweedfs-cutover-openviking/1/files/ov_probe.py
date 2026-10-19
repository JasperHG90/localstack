# Runs inside the OpenViking image. Mounts AGFS's s3fs backend exactly as
# service/core.py does (S3Config -> create_agfs_client) and drives every file
# operation VikingFS uses on it. Exits 0 only if all of them succeed.
import os, sys, traceback
from openviking_cli.utils.config.agfs_config import AGFSConfig
from openviking.utils.agfs_utils import RagfsBindingConfig, create_agfs_client
from openviking.pyagfs.helpers import cp
ak, sk, ep = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = AGFSConfig(backend="s3", path="/tmp/ovdata", s3={
    "bucket": "openviking", "endpoint": ep, "region": "us-east-1",
    "access_key": ak, "secret_key": sk, "use_ssl": False, "use_path_style": True})
c = create_agfs_client(RagfsBindingConfig(agfs=cfg))
print("mounts:", c.mounts())
ok = True
def step(label, fn):
    global ok
    try:
        r = fn(); print(f"PASS {label}: {str(r)[:160]}"); return r
    except Exception as e:
        ok = False; print(f"FAIL {label}: {type(e).__name__}: {e}")
R = "/local/viking/default/resources/spike"
big = os.urandom(12 * 1024 * 1024)
step("mkdir", lambda: c.mkdir(R))
step("ensure_parent_dirs", lambda: c.ensure_parent_dirs(R + "/deep/x/y.md"))
step("write small", lambda: c.write(R + "/a.md", b"hello seaweed"))
step("write odd name", lambda: c.write(R + "/odd name+@#%.md", b"odd"))
step("write 12MB", lambda: c.write(R + "/big.bin", big))
step("read small", lambda: (c.read(R + "/a.md") == b"hello seaweed") or (_ for _ in ()).throw(AssertionError("content mismatch")))
step("read 12MB intact", lambda: (bytes(c.read(R + "/big.bin")) == big) or (_ for _ in ()).throw(AssertionError("big mismatch")))
step("read range", lambda: (bytes(c.read(R + "/a.md", 6, 6)) == b"seawee") or (_ for _ in ()).throw(AssertionError("range mismatch")))
step("read odd name", lambda: c.read(R + "/odd name+@#%.md"))
step("stat file", lambda: c.stat(R + "/a.md"))
step("stat dir", lambda: c.stat(R))
step("ls", lambda: sorted(e["name"] for e in c.ls(R)))
step("touch", lambda: c.touch(R + "/t.md"))
step("create", lambda: c.create(R + "/empty.md"))
step("copy_within_mount", lambda: c.copy_within_mount(R + "/a.md", R + "/copy.md"))
step("read copy", lambda: c.read(R + "/copy.md"))
step("mv file", lambda: c.mv(R + "/copy.md", R + "/moved.md"))
step("write in deep dir", lambda: c.write(R + "/deep/x/y.md", b"deep seaweed"))
# VikingFS.mv on a directory is stat + helpers.cp(recursive) + rm(recursive),
# never the binding's own mv, so that is the path checked here.
step("stat dir for mv", lambda: c.stat(R + "/deep"))
step("cp -r (VikingFS.mv)", lambda: cp(c, R + "/deep", R + "/deep2", recursive=True))
step("rm -r source (VikingFS.mv)", lambda: c.rm(R + "/deep", recursive=True))
step("read moved deep file", lambda: (bytes(c.read(R + "/deep2/x/y.md")) == b"deep seaweed") or (_ for _ in ()).throw(AssertionError("deep mismatch")))
try:
    c.mv(R + "/deep2", R + "/deep3"); print("INFO raw binding mv dir: ok")
except Exception as e:
    print(f"INFO raw binding mv dir (not used by OpenViking): {type(e).__name__}: {e}")
step("tree", lambda: len(c.tree_directory(R)))
step("glob", lambda: c.glob_directory(R, "*.md"))
step("grep", lambda: c.grep(R, "seaweed", recursive=True))
step("rm file", lambda: c.rm(R + "/t.md"))
step("rm -r", lambda: c.rm(R, recursive=True))
def gone():
    try:
        c.stat(R + "/a.md")
    except Exception:
        return "gone"
    raise AssertionError("still there after rm -r")
step("stat after rm", gone)
print("RESULT", "ok" if ok else "FAILED")
sys.exit(0 if ok else 1)
