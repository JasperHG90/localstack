"""Runs inside the stub container: makes a VK, calls rerank (bare strings and
objects) and embeddings through Bifrost, prints one JSON summary."""
import base64, json, sys, time, urllib.error, urllib.request

BASE = "http://spike-bf:8080"
ADMIN = {"Authorization": "Basic " + base64.b64encode(b"admin:spikepass123").decode(),
         "content-type": "application/json"}

def call(path, body=None, headers=ADMIN):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers=headers, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, repr(e)

for _ in range(60):
    if call("/health")[0] == 200:
        break
    time.sleep(1)

st, raw = call("/api/governance/virtual-keys", {"name": "openviking", "provider_configs": [
    {"provider": "embark", "allowed_models": ["*"], "key_ids": ["*"], "weight": 1}]})
if st != 200:
    print(json.dumps({"vk_create": [st, raw]})); sys.exit(0)
vk = json.loads(raw)["virtual_key"]["value"]
inf = {"x-bf-vk": vk, "content-type": "application/json"}
out = {}
q = "what is the capital of France"
for label, docs in (("rerank_bare", ["Paris is the capital of France", "bananas are yellow"]),
                    ("rerank_objects", [{"text": "Paris is the capital of France"}, {"text": "bananas are yellow"}])):
    st, raw = call("/v1/rerank", {"model": "embark/reranker", "query": q, "documents": docs}, inf)
    out[label] = {"status": st, "body": raw[:600]}
st, raw = call("/v1/embeddings", {"model": "embark/embedding", "input": "dimension probe"}, inf)
routing = None
try:
    routing = json.loads(raw).get("extra_fields", {}).get("routing_info")
except Exception:
    pass
out["embeddings"] = {"status": st, "routing_info": routing, "body": raw[:300] if st != 200 else "(ok)"}
out["stub_log"] = [json.loads(l) for l in open("/tmp/stub.log")] if __import__("os").path.exists("/tmp/stub.log") else []
print(json.dumps(out))
