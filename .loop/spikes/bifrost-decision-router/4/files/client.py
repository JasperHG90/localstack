# Counts classifier (/v1/systemone) calls per chat request and key under two
# configs that try to run the classifier for the router key only:
#   A: config.json global rules, with a priority-0 passthrough rule
#      `virtual_key_name != "router"` (no target provider/model) ahead of the
#      three complexity_tier rules.
#   B: the global rules deleted via the admin API, the three tier rules created
#      via the admin API with scope virtual_key and scope_id = router key ID.
# Exits 0 when at least one config gives 0 classifier calls on the other key
# and still routes the router key by tier.
import base64, json, sys, urllib.request

EP, MOCK = sys.argv[1], sys.argv[2]
AUTH = {"authorization": "Basic " + base64.b64encode(b"admin:spikepass123").decode()}
TIER_MODELS = ["clef:cloud", "gpt-oss:120b-cloud", "deepseek-v4.1-flash", "mistral-large-4"]
TIERS = [("SIMPLE", "gpt-oss:120b-cloud"), ("MEDIUM", "deepseek-v4.1-flash"), ("COMPLEX", "mistral-large-4")]


def call(method, url, body=None, headers=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"null")
        except ValueError:
            return e.code, raw.decode(errors="replace")


def rules():
    s, b = call("GET", EP + "/api/governance/routing-rules", headers=AUTH)
    lst = (b or {}).get("rules", b if isinstance(b, list) else []) if isinstance(b, (dict, list)) else []
    return s, lst


def show_rules():
    s, lst = rules()
    print("  rules in store:", s)
    for r in lst:
        print("   ", r.get("priority"), r.get("name"), r.get("scope"), r.get("scope_id"), r.get("cel_expression"), r.get("targets"))
    return lst


def run_cases(label):
    cases = [  # (key, prompt, requested model, expected served model)
        ("router", "say hi", "ollama/deepseek-v4.1-flash", "gpt-oss:120b-cloud"),
        ("router", "ZZMEDIUM summarise this", "ollama/gpt-oss:120b-cloud", "deepseek-v4.1-flash"),
        ("router", "ZZCOMPLEX prove this theorem", "ollama/deepseek-v4.1-flash", "mistral-large-4"),
        ("other", "say hi", "ollama/deepseek-v4.1-flash", "deepseek-v4.1-flash"),
        ("other", "ZZCOMPLEX prove this theorem", "ollama/deepseek-v4.1-flash", "deepseek-v4.1-flash"),
        ("other", "ZZMEDIUM summarise this", "ollama/gpt-oss:120b-cloud", "gpt-oss:120b-cloud"),
    ]
    routed_ok, per_key = True, {"router": 0, "other": 0}
    for key, prompt, model, want in cases:
        before = call("GET", MOCK + "/_log")[1]
        s, b = call("POST", EP + "/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": prompt}]},
                    {"x-bf-vk": keys[key]})
        after = call("GET", MOCK + "/_log")[1]
        n = sum(1 for e in after[len(before):] if e["path"].endswith("/v1/systemone"))
        per_key[key] += n
        got = b["choices"][0]["message"]["content"].removeprefix("served-by:") if s == 200 else None
        ri = b.get("extra_fields", {}).get("routing_info") if isinstance(b, dict) else None
        good = got == want
        routed_ok &= good
        print(f"  [{'OK' if good else 'FAIL'}] {label} key={key} prompt={prompt!r} asked={model} status={s} "
              f"served={got} want={want} classifier_calls={n}")
        if not good:
            print("        body:", json.dumps(b)[:400])
        elif ri:
            print("        routing_info:", json.dumps(ri))
    ok = routed_ok and per_key["other"] == 0 and per_key["router"] == 3
    print(f"  {label}: classifier calls router={per_key['router']}/3 other={per_key['other']}/3 "
          f"routing_ok={routed_ok} -> {'WORKS' if ok else 'DOES NOT WORK'}")
    return ok


keys, ids = {}, {}
for name in ("router", "other"):
    s, b = call("POST", EP + "/api/governance/virtual-keys", {
        "name": name, "provider_configs": [{"provider": "ollama", "allowed_models": TIER_MODELS, "key_ids": ["*"], "weight": 1}]}, AUTH)
    vk = (b or {}).get("virtual_key", {})
    print(f"create vk {name}: {s} id={vk.get('id')}")
    keys[name], ids[name] = vk.get("value"), vk.get("id")

print("=== A: global rules from config.json, priority-0 passthrough for non-router keys ===")
show_rules()
a_ok = run_cases("A")

print("=== B: virtual_key-scoped tier rules via admin API, no global rules ===")
for r in rules()[1]:
    s, b = call("DELETE", EP + "/api/governance/routing-rules/" + r["id"], headers=AUTH)
    print(f"  delete {r['name']}: {s} {json.dumps(b)[:200] if s != 200 else ''}")
for i, (tier, model) in enumerate(TIERS, 1):
    s, b = call("POST", EP + "/api/governance/routing-rules", {
        "name": f"router-vk-{tier.lower()}", "scope": "virtual_key", "scope_id": ids["router"], "priority": i,
        "cel_expression": f'complexity_tier == "{tier}"',
        "targets": [{"provider": "ollama", "model": model, "weight": 1}]}, AUTH)
    print(f"  create router-vk-{tier.lower()}: {s} {json.dumps(b)[:300] if s not in (200, 201) else ''}")
lst = show_rules()
b_ok = run_cases("B") if any(r.get("scope") == "virtual_key" for r in lst) and not any(r.get("scope") == "global" for r in lst) else False

print(f"RESULT: A(passthrough rule)={'works' if a_ok else 'fails'} B(virtual_key scope)={'works' if b_ok else 'fails'}")
print("RISK DOES NOT HOLD" if (a_ok or b_ok) else "RISK HOLDS")
sys.exit(0 if (a_ok or b_ok) else 1)
