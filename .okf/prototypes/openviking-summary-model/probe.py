import json, os, sys, time, urllib.request, urllib.error
KEY = os.environ["BIFROST_KEY"]
variants = {
    "default": {},
    "effort=none": {"reasoning_effort": "none"},
    "effort=low": {"reasoning_effort": "low"},
    "think=false": {"think": False},
    "reasoning.enabled=false": {"reasoning": {"enabled": False}},
}
for model in sys.argv[1:]:
    for name, extra in variants.items():
        body = {"model": model, "max_tokens": 1500,
                "messages": [{"role": "user", "content": "In one sentence: why is the sky blue?"}], **extra}
        req = urllib.request.Request("http://192.168.2.50:8080/v1/chat/completions", json.dumps(body).encode(),
                                     {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        t = time.monotonic()
        try:
            d = json.load(urllib.request.urlopen(req, timeout=180))
            m = d["choices"][0]["message"]; u = d.get("usage", {})
            r = m.get("reasoning") or m.get("reasoning_content") or ""
            print(f"{model:24} {name:24} {time.monotonic()-t:5.1f}s out={u.get('completion_tokens')} "
                  f"reasoning_chars={len(r)} details={u.get('completion_tokens_details')}")
        except urllib.error.HTTPError as e:
            print(f"{model:24} {name:24} HTTP {e.code} {e.read().decode()[:150]}")
