# Creates the two virtual keys, sends chat requests, checks which model served
# each, and exits 0 only when routing is scoped to the router key by tier.
import base64, json, sys, urllib.request

EP, MOCK = sys.argv[1], sys.argv[2]
AUTH = "Basic " + base64.b64encode(b"admin:spikepass123").decode()
TIER_MODELS = ["clef:cloud", "gpt-oss:120b-cloud", "deepseek-v4.1-flash", "mistral-large-4"]


def call(method, url, body=None, headers=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


keys = {}
for name in ("router", "other"):
    s, b = call("POST", EP + "/api/governance/virtual-keys", {
        "name": name, "provider_configs": [{"provider": "ollama", "allowed_models": TIER_MODELS, "key_ids": ["*"], "weight": 1}]},
        {"authorization": AUTH})
    vk = (b or {}).get("virtual_key", {})
    print(f"create vk {name}: {s} id={vk.get('id')}")
    keys[name] = vk.get("value")

s, b = call("GET", EP + "/api/governance/routing-rules", headers={"authorization": AUTH})
print("routing rules in store:", s, json.dumps([(r.get("name"), r.get("scope"), r.get("cel_expression"), r.get("targets"))
                                                 for r in (b or {}).get("rules", b if isinstance(b, list) else [])]))

cases = [  # (key, prompt, requested model, expected served model)
    ("router", "say hi", "ollama/deepseek-v4.1-flash", "gpt-oss:120b-cloud"),
    ("router", "ZZMEDIUM summarise this", "ollama/gpt-oss:120b-cloud", "deepseek-v4.1-flash"),
    ("router", "ZZCOMPLEX prove this theorem", "ollama/deepseek-v4.1-flash", "mistral-large-4"),
    ("other", "say hi", "ollama/deepseek-v4.1-flash", "deepseek-v4.1-flash"),
    ("other", "ZZCOMPLEX prove this theorem", "ollama/deepseek-v4.1-flash", "deepseek-v4.1-flash"),
]
ok = True
for key, prompt, model, want in cases:
    s, b = call("POST", EP + "/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": prompt}]},
                {"x-bf-vk": keys[key]})
    got = None
    if s == 200:
        got = b["choices"][0]["message"]["content"].removeprefix("served-by:")
    ri = (b or {}).get("extra_fields", {}).get("routing_info") if isinstance(b, dict) else None
    good = got == want
    ok &= good
    print(f"[{'OK' if good else 'FAIL'}] key={key} prompt={prompt!r} asked={model} status={s} served={got} want={want}")
    print("      routing_info:", json.dumps(ri) if ri else json.dumps(b)[:400])

s, log = call("GET", MOCK + "/_log")
print("mock log:")
for e in log:
    print("  ", json.dumps(e)[:600])
decisions = [e for e in log if e["path"].endswith("/v1/systemone")]
print("decision calls:", len(decisions), "for", len(cases), "chat requests; models:", sorted({e["model"] for e in decisions}))
print("tier values Bifrost offered:", decisions[0]["criteria_keys"] if decisions else None)
print("classifier calls on the 'other' key (requests 4-5):", [e["tier"] for e in decisions[3:]])
print("RISK DOES NOT HOLD" if ok else "RISK HOLDS")
sys.exit(0 if ok else 1)
