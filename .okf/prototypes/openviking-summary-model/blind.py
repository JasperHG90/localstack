"""Shuffle the three summary versions per directory into blind/caseN/{A,B,C}.md
beside SOURCE.md, normalize link targets so none gives its model away, and
write the label-to-model key to blind_key.json. Run after fetch.py and gen.py."""

import json
import pathlib
import random
import re

random.seed(7)
data = json.loads(pathlib.Path("data.json").read_text())
blind = pathlib.Path("blind")
key = {}
for i, item in enumerate(data, 1):
    name = item["dir"].rsplit("/", 1)[1]
    case = blind / f"case{i}"
    case.mkdir(parents=True, exist_ok=True)
    (case / "SOURCE.md").write_text(
        "\n\n".join(f"===== FILE: {f['name']}\n{f['L2']}" for f in item["files"]))
    versions = {"flashlite": f"## L0\n{item['L0']}\n\n## L1\n{item['L1']}\n"}
    for model in ("gemma", "inkling"):
        text = (pathlib.Path("gen") / model / f"{name}.md").read_text()
        versions[model] = text[text.index("## L0"):]
    labels = ["A", "B", "C"]
    random.shuffle(labels)
    key[f"case{i}"] = {}
    for label, (model, text) in zip(labels, versions.items()):
        (case / f"{label}.md").write_text(re.sub(r"\]\(viking://[^)]*\)", "](link)", text))
        key[f"case{i}"][label] = model
pathlib.Path("blind_key.json").write_text(json.dumps(key, indent=1))
