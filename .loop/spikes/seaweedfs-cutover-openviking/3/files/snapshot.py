"""Snapshot OpenViking's tree and sample content hashes through its API.

Usage: snapshot.py OUT_DIR [SAMPLE_FILE]. Writes OUT_DIR/listing.txt (every
uri with dir/file flag, sorted) and OUT_DIR/hashes.txt (sha256 of each sampled
file as the API serves it). Without SAMPLE_FILE it picks 25 files spread over
the listing and writes them to OUT_DIR/sample.txt.
"""
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request

U = "https://openviking-api.lab.orangecluster.nl"
H = {"Authorization": f"Bearer {os.environ['OV_TOKEN']}"}
out = sys.argv[1]


def get(path: str, **q: object) -> bytes:
    url = f"{U}{path}?{urllib.parse.urlencode(q)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120) as r:
        return r.read()


entries = json.loads(get("/api/v1/fs/ls", uri="viking://", recursive="true", output="original", show_all_hidden="true"))["result"]
listing = sorted(f"{'d' if e['isDir'] else 'f'} {e['uri']}" for e in entries)
open(f"{out}/listing.txt", "w").write("\n".join(listing) + "\n")
files = [line[2:] for line in listing if line.startswith("f ")]
dirs = [line[2:] for line in listing if line.startswith("d ")]
children = {d: 0 for d in dirs}
for e in entries:
    parent = e["uri"].rstrip("/").rsplit("/", 1)[0]
    if parent in children:
        children[parent] += 1
empty = sorted(d for d, n in children.items() if n == 0)
if len(sys.argv) > 2:
    sample = open(sys.argv[2]).read().split()
else:
    step = max(1, len(files) // 25)
    sample = files[::step][:25]
    open(f"{out}/sample.txt", "w").write("\n".join(sample) + "\n")
hashes = [f"{hashlib.sha256(get('/api/v1/content/download', uri=u)).hexdigest()} {u}" for u in sample]
open(f"{out}/hashes.txt", "w").write("\n".join(hashes) + "\n")
digest = hashlib.sha256("\n".join(listing).encode()).hexdigest()
print(f"entries {len(listing)}: {len(files)} files, {len(dirs)} dirs, {len(empty)} empty dirs; listing sha256 {digest}")
print("empty dirs:", empty[:10], "..." if len(empty) > 10 else "")
print("\n".join(hashes))
