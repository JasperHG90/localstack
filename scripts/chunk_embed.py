#!/usr/bin/env python3
"""Chunk a document into roughly equal pieces and embed each through Bifrost.

Splits on blank lines first, and cuts a paragraph only when it alone exceeds
the target, on a word boundary. Reports per-chunk latency and then the closest
and furthest chunk pairs, which is the cheap check that the vectors carry
signal rather than merely arriving fast.

Latency on a second run of an unchanged document reflects embark's Redis
cache, not the model: only the chunks whose text actually moved will show a
cold number. Change --target-chars to re-measure honestly.

    BIFROST_VK   a Bifrost virtual key (secret/default/hermes/bifrost)

Read from the environment when set, otherwise from Vault.

Usage:
    python3 scripts/chunk_embed.py <path.md>
    python3 scripts/chunk_embed.py <path.md> --target-chars 1500
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import statistics
import subprocess
import sys
import time
import urllib.request
from typing import Any

BIFROST_URL = "http://192.168.2.50:8080/v1/embeddings"
MODEL = "embark/embedding"


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


def chunk(text: str, target: int) -> list[str]:
    """Paragraph-aligned chunks of roughly `target` characters."""
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        # A paragraph bigger than the target is cut on its own; nothing else
        # would keep the sizes even. Cut on whitespace, never mid-word: a
        # chunk that opens "s the promise." embeds the fragment, and the
        # vector lands away from every neighbour for a reason that is an
        # artifact of the split rather than anything in the document.
        if len(para) > target:
            if current:
                chunks.append(current)
                current = ""
            piece = ""
            for word in para.split():
                if piece and len(piece) + len(word) + 1 > target:
                    chunks.append(piece)
                    piece = word
                else:
                    piece = f"{piece} {word}" if piece else word
            if piece:
                chunks.append(piece)
            continue
        if current and len(current) + len(para) + 2 > target:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def embed(text: str, vk: str) -> tuple[list[float], float]:
    body = json.dumps({"model": MODEL, "input": text}).encode()
    req = urllib.request.Request(
        BIFROST_URL,
        data=body,
        headers={"Content-Type": "application/json", "x-bf-vk": vk},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data: dict[str, Any] = json.load(resp)
    return data["data"][0]["embedding"], time.perf_counter() - start


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--target-chars", type=int, default=1200)
    args = ap.parse_args()

    text = pathlib.Path(args.path).read_text(encoding="utf-8")
    chunks = chunk(text, args.target_chars)

    vk = os.environ.get("BIFROST_VK") or vault_field(
        "secret/default/hermes/bifrost", "API_KEY"
    )
    if not vk:
        print("no BIFROST_VK and vault read failed", file=sys.stderr)
        return 1

    sizes = [len(c) for c in chunks]
    print(f"{args.path}")
    print(f"  {len(text)} chars -> {len(chunks)} chunks, target {args.target_chars}")
    print(
        f"  chunk size: min {min(sizes)}  "
        f"median {int(statistics.median(sizes))}  max {max(sizes)}"
    )

    print(f"\n  {'#':>3}  {'chars':>6}  {'latency':>9}  first line")
    print(f"  {'-' * 3}  {'-' * 6}  {'-' * 9}  {'-' * 44}")
    vectors: list[list[float]] = []
    times: list[float] = []
    for i, c in enumerate(chunks):
        vec, elapsed = embed(c, vk)
        vectors.append(vec)
        times.append(elapsed)
        head = c.splitlines()[0][:44] if c.splitlines() else ""
        print(f"  {i:>3}  {len(c):>6}  {elapsed * 1000:>7.1f}ms  {head}")

    total = sum(times)
    print(
        f"\n  {len(chunks)} chunks in {total:.2f}s  "
        f"(median {statistics.median(times) * 1000:.1f}ms, "
        f"{len(text) / total:,.0f} chars/s)"
    )
    print(f"  dims {len(vectors[0])}")

    pairs = [
        (cosine(vectors[i], vectors[j]), i, j)
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
    ]
    if pairs:
        pairs.sort(reverse=True)
        print("\n  closest chunk pairs")
        for sim, i, j in pairs[:3]:
            print(f"    {i:>3} <-> {j:<3}  cos {sim:.4f}")
        print("  furthest")
        for sim, i, j in pairs[-2:]:
            print(f"    {i:>3} <-> {j:<3}  cos {sim:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
