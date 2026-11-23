"""Compare VLMs through Bifrost on real images.

Usage: BIFROST_KEY=... python3 bench.py LABEL MODEL EXTRA_JSON IMAGE...
Pass 1: one call per image, sequential; answers saved to out/LABEL/<image>.txt.
Pass 2: N calls (default 50) cycling over the images at CONC parallel (default 8).
"""

import base64
import concurrent.futures as cf
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

BASE = "http://192.168.2.50:8080/v1/chat/completions"
KEY = os.environ["BIFROST_KEY"]
N = int(os.environ.get("N", "50"))
CONC = int(os.environ.get("CONC", "8"))
PROMPT = 'Please analyze this image and generate three-layer information.\n\nProcessing Instruction: Understand image content\nSurrounding Text Context: No context\n\nPlease output in JSON format:\n{\n    "abstract": "Concise description (no more than 50 words), explaining what this image is",\n    "overview": "Detailed understanding (no more than 300 words), explaining the image\'s content, meaning, and important information",\n    "detail_text": "Text description that can replace the image (complete description of the information conveyed by the image, so that people who cannot see the image can also understand)"\n}\n'


def call(model, extra, image):
    b64 = base64.b64encode(pathlib.Path(image).read_bytes()).decode()
    body = {
        "model": model,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
        **extra,
    }
    req = urllib.request.Request(BASE, json.dumps(body).encode(), {
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
        msg = d["choices"][0]["message"]
        u = d.get("usage", {})
        return (time.monotonic() - t, 200, (msg.get("content") or "").strip(),
                u.get("prompt_tokens"), u.get("completion_tokens"))
    except urllib.error.HTTPError as e:
        return time.monotonic() - t, e.code, e.read().decode()[:300], None, None
    except Exception as e:
        return time.monotonic() - t, 0, repr(e)[:300], None, None


def main():
    label, model, extra, *images = sys.argv[1:]
    extra = json.loads(extra)
    out = pathlib.Path("out") / label
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== {label}: {model} {extra}")
    for img in images:
        s, code, text, tin, tout = call(model, extra, img)
        name = pathlib.Path(img).name
        (out / f"{name}.txt").write_text(text)
        print(f"  {name:42} {s:5.1f}s {code} in={tin} out={tout} chars={len(text)}")
    t = time.monotonic()
    with cf.ThreadPoolExecutor(CONC) as ex:
        res = list(ex.map(lambda i: call(model, extra, images[i % len(images)]), range(N)))
    wall = time.monotonic() - t
    lat = sorted(r[0] for r in res)
    codes = {}
    for r in res:
        codes[r[1]] = codes.get(r[1], 0) + 1
    print(f"  load {N} calls @ {CONC} parallel: wall {wall:.1f}s, "
          f"{N / wall * 60:.0f} img/min, p50 {lat[N // 2]:.1f}s, p95 {lat[int(N * .95)]:.1f}s, "
          f"max {lat[-1]:.1f}s, codes {codes}")
    errs = [r for r in res if r[1] != 200]
    if errs:
        print("  first error:", errs[0][2][:250])


main()
