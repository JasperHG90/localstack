#!/usr/bin/env bash
# Spike bifrost-update-2-6 risk 3: rerank (bare-string documents) and embeddings
# through an openai-based custom provider "embark", Bifrost 2.6.0 (control) vs 2.7.0.
# The upstream is a stub built from embark v0.2.4 (embark-jetson, as deployed)'s own image that validates
# every body with embark's RerankRequest / EmbeddingRequest models.
set -u
S=/home/vscode/spike-scratch/bifrost-27-2
EMBARK=ghcr.io/jasperhg90/embark-jetson:v0.2.4
cleanup() { docker rm -f spike-bf spike-stub >/dev/null 2>&1; docker network rm spikebf >/dev/null 2>&1; }
trap cleanup EXIT
for v in 2.6.0 2.7.0; do
  cleanup
  docker network create spikebf >/dev/null
  docker create --name spike-stub --network spikebf --entrypoint /app/.venv/bin/python -w /tmp "$EMBARK" /tmp/stub.py >/dev/null
  docker cp "$S/stub.py" spike-stub:/tmp/stub.py
  docker cp "$S/client.py" spike-stub:/tmp/client.py
  docker start spike-stub >/dev/null
  ip=$(docker inspect -f '{{(index .NetworkSettings.Networks "spikebf").IPAddress}}' spike-stub)
  sed "s/STUBIP/$ip/" "$S/config.json" > "$S/config.$v.json"
  docker create --name spike-bf --network spikebf -e BIFROST_ADMIN_USERNAME=admin \
    -e BIFROST_ADMIN_PASSWORD=spikepass123 -e EMBARK_API_KEY=stubkey "maximhq/bifrost:v$v" >/dev/null
  docker cp "$S/config.$v.json" spike-bf:/app/data/config.json
  docker start spike-bf >/dev/null
  docker exec spike-stub /app/.venv/bin/python /tmp/client.py 2>/dev/null > "$S/result.$v.json"
  echo "=== bifrost $v (stub at $ip) ==="
  cat "$S/result.$v.json"
done
python3 - "$S" <<'PY'
import json, sys
S = sys.argv[1]
res = {v: json.load(open(f"{S}/result.{v}.json")) for v in ("2.6.0", "2.7.0")}
def rerank_bodies(r):
    return [json.loads(e["body"]) | {"_status": e["embark_status"], "_path": e["path"]}
            for e in r.get("stub_log", []) if "rerank" in e["path"]]
for v, r in res.items():
    print(f"--- {v}: rerank_bare {r.get('rerank_bare',{}).get('status')}, rerank_objects "
          f"{r.get('rerank_objects',{}).get('status')}, embeddings {r.get('embeddings',{}).get('status')} "
          f"routing_info {r.get('embeddings',{}).get('routing_info')}")
    for b in rerank_bodies(r):
        print("   stub got rerank:", json.dumps(b, sort_keys=True))
new = res["2.7.0"]
emb = new.get("embeddings", {})
ri = emb.get("routing_info") or {}
ok = (new.get("rerank_bare", {}).get("status") == 200
      and bool(rerank_bodies(new)) and all(b["_status"] == 200 for b in rerank_bodies(new))
      and emb.get("status") == 200 and ri.get("provider") == "embark")
same = [{k: v for k, v in b.items() if k != "_status"} for b in rerank_bodies(res["2.6.0"])] == \
       [{k: v for k, v in b.items() if k != "_status"} for b in rerank_bodies(new)]
print("rerank bodies at embark identical between 2.6.0 and 2.7.0:", same)
print("RISK HOLDS" if not ok else "risk does not hold on 2.7.0")
sys.exit(0 if ok else 1)
PY
