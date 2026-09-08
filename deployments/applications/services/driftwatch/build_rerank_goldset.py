#!/usr/bin/env python3
"""Build `rerank-goldset.jsonl` from embark's own triplet gold set.

The rerank set is committed rather than generated at runtime, so this script
exists to make that file reproducible rather than hand-maintained. Run it when
`goldset.jsonl` changes: the two must cover the same queries, and
`test_the_rerank_pool_holds_the_hard_negative_for_its_query` fails when they
drift apart.

It needs a checkout of embark, which is a separate private repository:

    ./build_rerank_goldset.py ~/src/embark/goldsets/embark-docs/eval.jsonl

Deterministic by construction: no sampling, no shuffle, no clock. Running it
twice on the same input writes the same bytes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

POOL_SIZE = 10
NEIGHBORS = (1, 2, 3, 4)
STRIDE = 2
QUERIES = 30


def build(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Turn embark's triplets into one fixed candidate pool per query.

    Every second row, capped at `QUERIES`, matching how `goldset.jsonl` samples
    the same file: the two sets have to cover the same queries.

    Each pool is the row's own answer, the hard negative embark hand-authored
    to shadow it, then the four following rows contributing their negative
    before their positive, wrapping at the end. Fixed offsets rather than a
    sample so the file regenerates byte for byte.

    The pool is then rotated LEFT by the row's index modulo the pool size, so
    the answer sits at a different slot in every row. Without that it would sit
    at index 0 throughout and an off-by-one in the rank arithmetic would score
    a perfect run.
    """
    picked = rows[::STRIDE][:QUERIES]
    count = len(picked)
    out: list[dict[str, object]] = []

    for index, row in enumerate(picked):
        pool = [row["positive"], row["negative"]]
        for offset in NEIGHBORS:
            neighbor = picked[(index + offset) % count]
            pool.append(neighbor["negative"])
            pool.append(neighbor["positive"])
        pool = pool[:POOL_SIZE]
        if len(set(pool)) != POOL_SIZE:
            raise SystemExit(f"row {index}: pool holds a duplicate document")
        shift = index % POOL_SIZE
        pool = pool[shift:] + pool[:shift]
        out.append({"query": row["query"], "positive": row["positive"], "candidates": pool})

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="embark's goldsets/embark-docs/eval.jsonl")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "rerank-goldset.jsonl",
        help="where to write (default: beside this script)",
    )
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    built = build(rows)
    args.out.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in built),
        encoding="utf-8",
    )
    print(f"wrote {len(built)} rows to {args.out}")


if __name__ == "__main__":
    main()
