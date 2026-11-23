"""Regenerate OpenViking's L1/L0 for each directory in data.json with one model,
using OV 0.4.17.1's own prompts (semantic.document_summary, then
semantic.overview_generation; L0 = overview text before the first ##).

Usage: BIFROST_KEY=... python3 gen.py LABEL MODEL EXTRA_JSON TEMPLATE_DIR
"""

import json
import os
import pathlib
import re
import sys
import time
import urllib.request

BASE = "http://192.168.2.50:8080/v1/chat/completions"
KEY = os.environ["BIFROST_KEY"]
label, model, extra, tdir = sys.argv[1:]
extra = json.loads(extra)
tdir = pathlib.Path(tdir)


def template(name):
    text = (tdir / f"{name}.yaml").read_text()
    body = text.split("template: |\n", 1)[1].split("\nllm_config:", 1)[0]
    body = "\n".join(line[2:] for line in body.splitlines())
    # The overview template's only Jinja logic picks zh-CN headings.
    return re.sub(r'\{\{ "[^"]*" if output_language == "zh-CN" else "([^"]*)" \}\}', r"\1", body)


def render(tpl, **values):
    for k, v in values.items():
        tpl = tpl.replace("{{ " + k + " }}", v)
    return tpl


DOC = template("document_summary")
OVR = template("overview_generation")
stats = {"calls": 0, "seconds": 0.0, "out_tokens": 0}


def complete(prompt):
    body = {"model": model, "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}], **extra}
    req = urllib.request.Request(BASE, json.dumps(body).encode(), {
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t = time.monotonic()
    d = json.load(urllib.request.urlopen(req, timeout=300))
    stats["calls"] += 1
    stats["seconds"] += time.monotonic() - t
    stats["out_tokens"] += d.get("usage", {}).get("completion_tokens") or 0
    return (d["choices"][0]["message"].get("content") or "").strip()


def abstract(overview):
    lines, in_header = [], True
    for line in overview.split("\n"):
        if in_header and line.startswith("#"):
            continue
        if in_header and line.strip():
            in_header = False
        if not in_header:
            if line.startswith("##"):
                break
            if line.strip():
                lines.append(line.strip())
    return "\n".join(lines)


data = json.loads(pathlib.Path("data.json").read_text())
out = pathlib.Path("gen") / label
out.mkdir(parents=True, exist_ok=True)
for item in data:
    name = item["dir"].rsplit("/", 1)[1]
    summaries = []
    for idx, f in enumerate(item["files"], 1):
        content = f["L2"][:30000]
        s = complete(render(DOC, file_name=f["name"], content=content, output_language="en"))
        summaries.append(f"- {f['name']} (link: viking://input_sample_f{idx}): {s}")
    n = len(summaries)
    overview = complete(render(
        OVR, dir_name=name, output_language="en",
        directory_coverage=f"Total direct entries: {n}. All direct entries are represented in the summaries below.",
        file_summaries="\n".join(summaries), children_abstracts="None"))
    (out / f"{name}.md").write_text(
        "## FILE SUMMARIES\n" + "\n".join(summaries) + "\n\n## L0\n" + abstract(overview)
        + "\n\n## L1\n" + overview + "\n")
    print(f"  {name[:50]:50} files={n} L1_words={len(overview.split())} L0_words={len(abstract(overview).split())}")
print(f"{label}: {stats['calls']} calls, {stats['seconds']:.1f}s, {stats['out_tokens']} out tokens")
