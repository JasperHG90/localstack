# Runs inside the OpenViking container. Usage: drive.py PHASE SCHEMA DSN
# Writes a resource and two entity memories as lab/jasper, searches, and
# records two deltas through ov-postgres's PgDeltaStore (the path capture uses).
import json, sys, time, urllib.request
from datetime import datetime, timezone

phase, schema, dsn = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = "http://127.0.0.1:1933"
HDR = {"Content-Type": "application/json", "X-OpenViking-Account": "lab", "X-OpenViking-User": "jasper"}

def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=HDR, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]

uris = [f"viking://resources/spike/{phase}.md",
        f"viking://user/jasper/memories/entities/spike-{phase}-a.md",
        f"viking://user/jasper/memories/entities/spike-{phase}-b.md"]
for u in uris:
    code, res = post("/api/v1/content/write", {"uri": u, "content": f"# {phase}\nSpike note {phase} for {u}, about postgres schemas.", "mode": "create", "wait": True, "timeout": 120})
    print(f"write {u}: {code} {str(res)[:200]}")
time.sleep(3)
code, res = post("/api/v1/search/find", {"query": "postgres schemas spike note", "limit": 5})
hits = res.get("result", {}) if isinstance(res, dict) else res
print(f"find: {code} {json.dumps(hits)[:600]}")

from psycopg_pool import ConnectionPool
from ov_postgres.deltas import PgDeltaStore
from ov_ext.reflect.capture import MemoryDelta
pool = ConnectionPool(dsn, min_size=1, max_size=1, open=True)
store = PgDeltaStore(pool, schema)
now = datetime.now(timezone.utc)
store.record_sync([MemoryDelta(uri=u, memory_type="entities", field="content", search="", replace=f"spike {phase}", created=True, changed_at=now) for u in uris[1:]])
print("deltas recorded; pending:", len(store.pending(limit=50)))
pool.close()
