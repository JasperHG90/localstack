#!/usr/bin/env python3
"""Time embark's embedding endpoint across input lengths.

Reports median latency per input size, through Bifrost and, where reachable,
against embark directly. The gap between the two is the gateway's overhead.

By default each call carries a fresh nonce, because embark caches responses
in Redis keyed on the input: repeat one string and every length returns the
same number, which is the cache's latency and not the model's. `--cached`
measures that path deliberately.

    EMBARK_KEY   embark's own API key   (secret/default/embark/auth)
    BIFROST_VK   a Bifrost virtual key  (secret/default/hermes/bifrost)

Read from the environment when set, otherwise from Vault.

`--target direct` only works from a host embark's firewall admits, which is
radxa-dragon-q6a and the Jetson itself (deployments/applications/services.tf,
`local.firewall_rules.embark`). Everywhere else it times out, by design:
embark is reached through Bifrost. `--target bifrost` works from anywhere.

Usage:
    python3 scripts/embark_bench.py                       # via Bifrost
    python3 scripts/embark_bench.py --cached              # measure the cache
    python3 scripts/embark_bench.py --runs 20 --lengths 64,512,4096
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

EMBARK_URL = "http://192.168.2.46:8000/v1/embeddings"
BIFROST_URL = "http://192.168.2.50:8080/v1/embeddings"

# Lengths in characters, not tokens: embark does not report a token count and
# guessing a ratio would make the axis less honest than the thing measured.
DEFAULT_LENGTHS = (16, 64, 256, 1024, 2048, 4096)

# Repeated so a longer input is more text rather than one word padded out; a
# tokenizer collapses runs of the same character and the curve goes flat.
LOREM = (
    "the quick brown fox jumps over the lazy dog while a cluster of small "
    "machines quietly serves embeddings from a graphics processor nearby "
)


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


def text_of_length(n: int, nonce: int | None = None) -> str:
    """Text of exactly n characters, unique per nonce.

    The nonce is not cosmetic. embark caches responses in Redis keyed on the
    input, so repeating the same string measures a cache lookup and returns
    the same number for 16 characters and for 4096. Pass a fresh nonce per
    call to measure the model; pass None to measure the cache on purpose.
    """
    filler = LOREM * (n // len(LOREM) + 2)
    if nonce is None:
        return filler[:n]
    prefix = f"{nonce:08x} "
    return (prefix + filler)[:n] if n > len(prefix) else prefix[:n]


def post(
    url: str, payload: dict[str, Any], headers: dict[str, str]
) -> tuple[float, int]:
    """Return (elapsed seconds, embedding dimensions)."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    elapsed = time.perf_counter() - start
    return elapsed, len(data["data"][0]["embedding"])


def bench(
    url: str,
    model: str,
    headers: dict[str, str],
    lengths: Sequence[int],
    runs: int,
    cached: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    counter = int(time.time() * 1000) & 0xFFFFFFFF

    def call(n: int, nonce: int | None) -> tuple[float, int]:
        return post(url, {"model": model, "input": text_of_length(n, nonce)}, headers)

    for n in lengths:
        try:
            call(n, None if cached else counter)  # warm the path, not the timing
            if cached:
                times = [call(n, None)[0] for _ in range(runs)]
                dims = call(n, None)[1]
            else:
                times = []
                for _ in range(runs):
                    counter += 1
                    times.append(call(n, counter)[0])
                counter += 1
                dims = call(n, counter)[1]
        except urllib.error.HTTPError as e:
            rows.append(
                {"chars": n, "error": f"HTTP {e.code}: {e.read()[:120].decode()}"}
            )
            continue
        except Exception as e:  # noqa: BLE001 - a bench should report, not raise
            rows.append({"chars": n, "error": str(e)[:120]})
            continue
        rows.append(
            {
                "chars": n,
                "dims": dims,
                "min": min(times),
                "median": statistics.median(times),
                "max": max(times),
            }
        )
    return rows


def render(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n{title}")
    print(f"  {'chars':>6}  {'dims':>5}  {'min':>8}  {'median':>8}  {'max':>8}")
    print(f"  {'-' * 6}  {'-' * 5}  {'-' * 8}  {'-' * 8}  {'-' * 8}")
    for r in rows:
        if "error" in r:
            print(f"  {r['chars']:>6}  {r['error']}")
            continue
        print(
            f"  {r['chars']:>6}  {r['dims']:>5}  "
            f"{r['min'] * 1000:>7.1f}ms  {r['median'] * 1000:>7.1f}ms  {r['max'] * 1000:>7.1f}ms"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=10, help="timed calls per length")
    ap.add_argument("--lengths", help="comma-separated character counts")
    ap.add_argument(
        "--target", choices=("direct", "bifrost", "both"), default="bifrost"
    )
    ap.add_argument(
        "--cached",
        action="store_true",
        help="repeat one input per length to measure the Redis cache instead of the model",
    )
    args = ap.parse_args()

    lengths = (
        [int(x) for x in args.lengths.split(",")] if args.lengths else DEFAULT_LENGTHS
    )
    mode = " [cache hits]" if args.cached else " [cache misses]"

    if args.target in ("direct", "both"):
        key = os.environ.get("EMBARK_KEY") or vault_field(
            "secret/default/embark/auth", "api_key"
        )
        if not key:
            print("no EMBARK_KEY and vault read failed", file=sys.stderr)
            return 1
        render(
            f"embark direct ({EMBARK_URL}), {args.runs} runs/length{mode}",
            bench(
                EMBARK_URL,
                "embedding",
                {"Authorization": f"Bearer {key}"},
                lengths,
                args.runs,
                args.cached,
            ),
        )

    if args.target in ("bifrost", "both"):
        vk = os.environ.get("BIFROST_VK") or vault_field(
            "secret/default/hermes/bifrost", "API_KEY"
        )
        if not vk:
            print("no BIFROST_VK and vault read failed", file=sys.stderr)
            return 1
        render(
            f"via bifrost ({BIFROST_URL}), {args.runs} runs/length{mode}",
            bench(
                BIFROST_URL,
                "embark/embedding",
                {"x-bf-vk": vk},
                lengths,
                args.runs,
                args.cached,
            ),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
