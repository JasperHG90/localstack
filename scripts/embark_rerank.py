#!/usr/bin/env python3
"""Test embark's reranker through Bifrost.

Two modes. With no --file it runs a built-in relevance suite: each case is a
query, a set of documents, and the document that must come first. It asserts
the ordering rather than printing scores for a human to eyeball, so a model
that loads but ranks badly fails instead of looking fine.

With --file it chunks a real document and reranks the chunks against --query,
which is the shape a retrieval pipeline actually uses.

    BIFROST_VK   a Bifrost virtual key (secret/default/hermes/bifrost)

Read from the environment when set, otherwise from Vault.

Scores are raw cross-encoder logits and are usually negative. Only their order
means anything; the scale is the model's own and does not compare across
models.

Usage:
    python3 scripts/embark_rerank.py
    python3 scripts/embark_rerank.py --file doc.md --query "how does X work?"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chunk_embed import chunk

BIFROST_URL = "http://192.168.2.50:8080/v1/rerank"
MODEL = "embark/reranker"

# Each case is (query, documents, index that must rank first). The distractors
# are deliberately unrelated: this checks the model is wired up and scoring,
# not that it can make fine distinctions.
CASES: list[tuple[str, list[str], int]] = [
    (
        "How do I deploy a GPU workload on Nomad?",
        [
            "Chocolate chip cookies need butter, sugar and flour.",
            "Nomad jobs request GPU devices via nvidia-container-runtime.",
            "The Rhine flows through Germany and the Netherlands.",
            "Use a constraint on attr.unique.hostname to pin a workload.",
        ],
        1,
    ),
    (
        "Which environment variables expose the GPU to a container?",
        [
            "Tulip bulbs are planted in autumn for a spring flowering.",
            "NVIDIA_VISIBLE_DEVICES and NVIDIA_DRIVER_CAPABILITIES expose the GPU.",
            "HAProxy terminates TLS at the cluster edge.",
        ],
        1,
    ),
    (
        "Where are the model artifacts stored?",
        [
            "A prestart task unpacks each ModelKit into the host volume.",
            "Bifrost load-balances two Ollama Cloud keys.",
            "The Orin Nano has six CPU cores.",
        ],
        0,
    ),
]


# Reported, never asserted. Each needs a step of domain inference rather than
# overlap with the query, which is a different question from whether the model
# is wired up. mxbai-rerank-xsmall ranks the first of these below an unrelated
# distractor, so the suite above would fail for a reason that says nothing
# about the deployment. Watch these when changing model, do not gate on them.
PROBES: list[tuple[str, list[str], int]] = [
    (
        "What causes a container to fall back to the CPU?",
        [
            "Tulip bulbs are planted in autumn for a spring flowering.",
            "Set NVIDIA_VISIBLE_DEVICES or the runtime injects no libcuda.",
            "HAProxy terminates TLS at the cluster edge.",
        ],
        1,
    ),
]


def vault_field(path: str, field: str) -> str | None:
    try:
        out = subprocess.run(
            ["vault", "kv", "get", f"-field={field}", path],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def rerank(
    query: str, documents: list[str], vk: str, top_n: int | None = None
) -> tuple[list[dict[str, Any]], float]:
    """Return (results ordered best first, elapsed seconds).

    Bifrost requires documents as objects carrying a `text` field. Passing
    bare strings, which embark itself accepts, is rejected by the gateway
    with a bare "Invalid request payload" and no routing information.
    """
    payload: dict[str, Any] = {
        "model": MODEL,
        "query": query,
        "documents": [{"id": str(i), "text": d} for i, d in enumerate(documents)],
    }
    if top_n is not None:
        payload["top_n"] = top_n
    req = urllib.request.Request(
        BIFROST_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-bf-vk": vk},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        body: dict[str, Any] = json.load(resp)
    return body["results"], time.perf_counter() - start


def run_suite(vk: str) -> int:
    failures = 0
    for query, docs, expected in CASES:
        results, elapsed = rerank(query, docs, vk)
        winner = results[0]["index"]
        ok = winner == expected
        failures += 0 if ok else 1
        print(f"\n  {'PASS' if ok else 'FAIL'}  {query}")
        print(f"        {len(docs)} docs, {elapsed * 1000:.0f}ms")
        for rank, r in enumerate(results):
            mark = "<-- expected first" if r["index"] == expected else ""
            print(
                f"        {rank + 1}. [{r['index']}] "
                f"{r['relevance_score']:+8.3f}  {docs[r['index']][:52]} {mark}"
            )
    print(f"\n  {len(CASES) - failures}/{len(CASES)} cases ranked correctly")

    print("\n  probes (reported, not asserted)")
    for query, docs, expected in PROBES:
        results, _ = rerank(query, docs, vk)
        got = results[0]["index"]
        verdict = "ranks as hoped" if got == expected else "ranks the target lower"
        print(f"    {verdict}: {query}")
        for rank, r in enumerate(results):
            mark = "<-- hoped first" if r["index"] == expected else ""
            print(
                f"      {rank + 1}. {r['relevance_score']:+8.3f}  "
                f"{docs[r['index']][:50]} {mark}"
            )
    return failures


def run_file(path: str, query: str, vk: str, target: int, top_n: int) -> int:
    text = Path(path).read_text(encoding="utf-8")
    chunks = chunk(text, target)
    results, elapsed = rerank(query, chunks, vk, top_n=top_n)
    print(f"\n  {path}")
    print(f"  {len(text)} chars -> {len(chunks)} chunks, reranked in {elapsed:.2f}s")
    print(f"  query: {query}\n")
    for rank, r in enumerate(results):
        head = " ".join(chunks[r["index"]].split())[:66]
        print(f"    {rank + 1}. [{r['index']:>2}] {r['relevance_score']:+8.3f}  {head}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="rerank this document's chunks instead")
    ap.add_argument("--query", help="required with --file")
    ap.add_argument("--target-chars", type=int, default=1200)
    ap.add_argument("--top-n", type=int, default=5)
    args = ap.parse_args()

    if args.file and not args.query:
        print("--file needs --query", file=sys.stderr)
        return 2

    vk = os.environ.get("BIFROST_VK") or vault_field(
        "secret/default/hermes/bifrost", "API_KEY"
    )
    if not vk:
        print("no BIFROST_VK and vault read failed", file=sys.stderr)
        return 1

    if args.file:
        return run_file(args.file, args.query, vk, args.target_chars, args.top_n)
    return run_suite(vk)


if __name__ == "__main__":
    raise SystemExit(main())
