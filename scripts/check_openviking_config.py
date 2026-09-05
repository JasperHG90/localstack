#!/usr/bin/env python3
"""Assert the parts of OpenViking's config that must not drift.

The config is a Nomad template inside `services/openviking.hcl`, rendered with
Vault credentials at deploy time, so nothing else in this repo reads it. These
six settings each fail in a way a healthy-looking service would hide:

    dimension        a wrong value corrupts the collection silently
    backend          the vectordb one, not agfs's, which is declared first
    custom_params    ov-postgres forbids unknown keys; a typo fails at startup
    rerank target    pointing past Bifrost loses gateway governance
    auth_mode        anything but "oidc" drops Vault as the identity source
    audience         must equal client_id, or every token is refused

This is the STATIC half of the ticket's R15. It does not measure whether a live
Vault token is accepted, whether a foreign audience is refused, or whether any
call reaches embark. Those need a deployed service and no gate here runs one.

Run with `--self-test` to check the checker.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

JOBSPEC = Path("deployments/applications/services/openviking.hcl")

EXPECTED_DIMENSION = 768
EXPECTED_AUTH_MODE = "oidc"
EXPECTED_BACKEND = "ov_postgres.adapter.PgVectorCollectionAdapter"

# ov-postgres's config model is extra=forbid, so a key outside this set is a
# startup failure rather than a warning.
# Every field PgVectorParams declares, plus `schema`, which is `db_schema`'s
# alias. Read off the model at the pinned tag rather than from prose: a key
# this set omits is reported as forbidden while ov-postgres accepts it.
ALLOWED_CUSTOM_PARAMS = frozenset(
    {
        "dsn",
        "schema",
        "db_schema",
        "table_prefix",
        "index_method",
        "index_options",
        "create_extension",
        "iterative_scan",
        "distance",
        "keyword_fields",
        "text_search_config",
        "tz_policy",
        "min_pool_size",
        "max_pool_size",
        "connect_timeout",
        "application_name",
    }
)


def _value(text: str, key: str) -> str | None:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', text)
    return match.group(1) if match else None


def _custom_param_keys(text: str) -> set[str]:
    block = re.search(r'"custom_params"\s*:\s*\{(.*?)\n\s*\}', text, re.DOTALL)
    if not block:
        return set()
    return set(re.findall(r'"([a-z_]+)"\s*:', block.group(1)))


def _vectordb_backend(text: str) -> str | None:
    """The backend inside `vectordb`, not the first `backend` in the file.

    `agfs` declares its own `backend` earlier, so an unscoped lookup reads the
    blob store's value and passes whatever the vector store is set to.
    """
    block = re.search(r'"vectordb"\s*:\s*\{(.*?)\n\s{12}\}', text, re.DOTALL)
    return _value(block.group(1), "backend") if block else None


def failures(text: str) -> list[str]:
    found: list[str] = []

    dimension = re.search(r'"dimension"\s*:\s*(\d+)', text)
    if dimension is None or int(dimension.group(1)) != EXPECTED_DIMENSION:
        got = dimension.group(1) if dimension else "absent"
        found.append(
            f"embedding.dense.dimension is {got}, expected {EXPECTED_DIMENSION}. "
            "Measured against embark through Bifrost; a wrong value corrupts "
            "the collection without erroring."
        )

    backend = _vectordb_backend(text)
    if backend != EXPECTED_BACKEND:
        found.append(
            f"storage.vectordb.backend is {backend!r}, expected {EXPECTED_BACKEND!r}"
        )

    unknown = _custom_param_keys(text) - ALLOWED_CUSTOM_PARAMS
    if unknown:
        found.append(
            f"custom_params carries {sorted(unknown)}, which ov-postgres forbids "
            "(its config model is extra=forbid, so this fails at startup)"
        )

    rerank = re.search(r'"rerank"\s*:\s*\{(.*?)\n\s{10}\}', text, re.DOTALL)
    if rerank is None:
        found.append("no rerank section")
    elif "8080" not in rerank.group(1):
        found.append(
            "rerank.api_base does not point at Bifrost's port. Rerank must "
            "traverse the gateway; a direct embark target loses its logging, "
            "governance and virtual-key accounting."
        )

    auth_mode = _value(text, "auth_mode")
    if auth_mode != EXPECTED_AUTH_MODE:
        found.append(
            f"server.auth_mode is {auth_mode!r}, expected {EXPECTED_AUTH_MODE!r}. "
            "Anything else drops Vault as the identity source."
        )

    client_id = _value(text, "client_id")
    audience = _value(text, "audience")
    if client_id is None or audience is None or client_id != audience:
        found.append(
            f"server.oidc.audience ({audience!r}) must equal client_id "
            f"({client_id!r}); Vault sets a token's aud to the client id, so a "
            "mismatch refuses every token."
        )

    return found


# Mirrors the jobspec's nesting, including agfs declaring its own `backend`
# BEFORE vectordb does. A fixture with only one `backend` key passes an
# unscoped lookup that reads the blob store's value in the real file.
CLEAN = """
            "agfs": {
              "backend": "s3",
              "s3": { "bucket": "openviking" }
            },
            "vectordb": {
              "backend": "ov_postgres.adapter.PgVectorCollectionAdapter",
              "custom_params": {
                "dsn": "postgresql://u:p@h:5432/openviking",
                "schema": "openviking",
                "index_method": "flat"
              }
            },
  "embedding": { "dense": { "dimension": 768 } },
          "rerank": {
            "api_base": "http://192.168.2.50:8080/v1",
            "timeout": 120
          },
  "auth_mode": "oidc",
  "client_id": "abc123",
  "audience": "abc123"
"""


def _self_test() -> int:
    if failures(CLEAN):
        print(
            f"self-test: clean config was flagged: {failures(CLEAN)}", file=sys.stderr
        )
        return 1

    mutants = {
        "dimension": (
            CLEAN.replace('"dimension": 768', '"dimension": 512'),
            "dimension",
        ),
        "backend": (CLEAN.replace(EXPECTED_BACKEND, "local"), "backend"),
        "custom_params": (
            CLEAN.replace('"schema": "openviking"', '"schemaa": "openviking"'),
            "custom_params",
        ),
        "rerank": (CLEAN.replace("8080", "8000"), "rerank"),
        "auth_mode": (
            CLEAN.replace('"auth_mode": "oidc"', '"auth_mode": "api_key"'),
            "auth_mode",
        ),
        "audience": (
            CLEAN.replace('"audience": "abc123"', '"audience": "other"'),
            "audience",
        ),
    }
    for name, (text, marker) in mutants.items():
        hits = failures(text)
        if not any(marker in hit for hit in hits):
            print(
                f"self-test: the {name} mutant was not detected: {hits}",
                file=sys.stderr,
            )
            return 1

    print("self-test: ok")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()

    if not JOBSPEC.exists():
        print(f"{JOBSPEC}: not found", file=sys.stderr)
        return 1

    found = failures(JOBSPEC.read_text())
    for failure in found:
        print(f"{JOBSPEC}: {failure}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
