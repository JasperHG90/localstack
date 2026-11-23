"""Run OpenViking's own image prompt (vision.image_understanding, v0.4.17.1)
through Bifrost, sequentially, and check each answer parses as the JSON OV wants.

Usage: BIFROST_KEY=... python3 ovbench.py LABEL MODEL EXTRA_JSON IMAGE...
"""

import base64
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "http://192.168.2.50:8080/v1/chat/completions"
KEY = os.environ["BIFROST_KEY"]
PROMPT = """Please analyze this image and generate three-layer information.

Processing Instruction: Understand image content
Surrounding Text Context: No context

Please output in JSON format:
{
    "abstract": "Concise description (no more than 50 words), explaining what this image is",
    "overview": "Detailed understanding (no more than 300 words), explaining the image's content, meaning, and important information",
    "detail_text": "Text description that can replace the image (complete description of the information conveyed by the image, so that people who cannot see the image can also understand)"
}
"""


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return False
    return isinstance(d, dict) and {"abstract", "overview", "detail_text"} <= d.keys()


def main():
    label, model, extra, *images = sys.argv[1:]
    extra = json.loads(extra)
    out = pathlib.Path("ovout") / label
    out.mkdir(parents=True, exist_ok=True)
    total = 0.0
    ok = 0
    print(f"=== {label}: {model} {extra}")
    for img in images:
        b64 = base64.b64encode(pathlib.Path(img).read_bytes()).decode()
        body = {"model": model, "temperature": 0.0, "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}], **extra}
        req = urllib.request.Request(BASE, json.dumps(body).encode(), {
            "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        t = time.monotonic()
        try:
            d = json.load(urllib.request.urlopen(req, timeout=300))
            text = d["choices"][0]["message"].get("content") or ""
            out_tok = d.get("usage", {}).get("completion_tokens")
            code = 200
        except urllib.error.HTTPError as e:
            text, out_tok, code = e.read().decode()[:300], None, e.code
        s = time.monotonic() - t
        total += s
        good = code == 200 and parse(text)
        ok += good
        name = pathlib.Path(img).name
        (out / f"{name}.txt").write_text(text)
        print(f"  {name:42} {s:5.1f}s {code} out={out_tok} json_ok={good}")
    print(f"  total {total:.1f}s, valid JSON {ok}/{len(images)}")


main()
