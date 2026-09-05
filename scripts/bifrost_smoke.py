#!/usr/bin/env python3
"""Assert Bifrost's auth posture and its reach to embark, before and after a bump.

Run it against the OLD gateway and again against the NEW one. The before-run
is what makes the after-run mean anything: an assertion that only ever runs
after an upgrade cannot tell "the upgrade broke it" from "it was never true".

Five assertions, each exiting non-zero on the first failure so this works as a
gate rather than a report:

    1. inference auth is enforced (no key, and a bogus key, are both refused)
    2. /metrics is behind basic auth
    3. the admin API has no unauthenticated path
    4. every virtual key survives
    5. embeddings reach embark

Assertion 1 sends documents in the OBJECT form on purpose. Bifrost parses the
payload before it checks the virtual key, so a bare-string rerank returns 400
for a malformed body and never reaches the auth code at all on a gateway that
does not yet accept that shape. Sending objects holds the shape constant so
the gateway version is the only thing that varies between runs.

Credentials come from Vault and are never printed: admin basic auth from
`secret/default/bifrost/credentials`, a virtual key from
`secret/default/hermes/bifrost`.

Usage:
    python3 scripts/bifrost_smoke.py --base-url http://192.168.2.50:8080
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from functools import partial
from typing import Any

TIMEOUT = 30

# Named so a diff that drops one is visible. Two of these are not Terraform
# resources, so nothing would recreate them and `terraform plan` cannot see
# them going missing.
EXPECTED_VIRTUAL_KEYS = frozenset({"Leo", "hermes", "jasper-laptop-cc", "memex"})

EMBEDDING_DIMENSION = 768


class SmokeFailure(Exception):
    """An assertion failed. Carries no credential, deliberately."""


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


def request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    """Return (status, body). A 4xx/5xx is a result here, not an exception."""
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def basic_auth(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def rerank_body(documents: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "model": "embark/reranker",
        "query": "what is the capital of France",
        "documents": documents,
    }


def assert_inference_auth_enforced(base: str) -> None:
    objects = [
        {"text": "Paris is the capital of France"},
        {"text": "bananas are yellow"},
    ]
    for label, headers in (
        ("virtual_key_required", {}),
        ("virtual_key_not_found", {"x-bf-vk": "definitely-not-a-real-key"}),
    ):
        status, raw = request(
            f"{base}/v1/rerank",
            method="POST",
            body=rerank_body(objects),
            headers=headers,
        )
        if status != 401:
            raise SmokeFailure(
                f"inference auth: expected 401 for {label}, got {status}. "
                "A 200 means enforce_auth_on_inference stopped enforcing."
            )
        kind = json.loads(raw).get("type")
        if kind != label:
            raise SmokeFailure(
                f"inference auth: expected type {label!r}, got {kind!r}. "
                "The status alone does not distinguish a governance refusal "
                "from a transport-level 401."
            )


def assert_metrics_behind_basic_auth(base: str, user: str, password: str) -> None:
    status, _ = request(f"{base}/metrics")
    if status != 401:
        raise SmokeFailure(f"/metrics: expected 401 unauthenticated, got {status}")

    status, raw = request(f"{base}/metrics", headers=basic_auth(user, password))
    if status != 200:
        raise SmokeFailure(f"/metrics: expected 200 with basic auth, got {status}")
    if b"bifrost_" not in raw:
        raise SmokeFailure("/metrics: authenticated body carries no bifrost_ metrics")


def assert_no_unauthenticated_admin_path(base: str) -> None:
    for path in ("/api/governance/virtual-keys", "/api/providers", "/api/config"):
        status, _ = request(f"{base}{path}")
        if status != 401:
            raise SmokeFailure(
                f"admin API: expected 401 unauthenticated on {path}, got {status}. "
                "setup_token must not open a first-admin path on a store that "
                "already holds an admin."
            )


def assert_virtual_keys_survive(base: str, user: str, password: str) -> None:
    status, raw = request(
        f"{base}/api/governance/virtual-keys", headers=basic_auth(user, password)
    )
    if status != 200:
        raise SmokeFailure(f"virtual keys: expected 200, got {status}")
    payload = json.loads(raw)
    keys = payload.get("virtual_keys") or payload.get("data") or []
    names = {k.get("name") for k in keys}
    missing = EXPECTED_VIRTUAL_KEYS - names
    if missing:
        raise SmokeFailure(
            f"virtual keys: {sorted(missing)} absent. Nothing recreates the two "
            "that Terraform does not manage."
        )


def assert_embeddings_reach_embark(base: str, vk: str) -> None:
    status, raw = request(
        f"{base}/v1/embeddings",
        method="POST",
        body={"model": "embark/embedding", "input": "dimension probe"},
        headers={"x-bf-vk": vk},
    )
    if status != 200:
        raise SmokeFailure(f"embeddings: expected 200, got {status}")
    payload = json.loads(raw)
    vector = payload["data"][0]["embedding"]
    if len(vector) != EMBEDDING_DIMENSION:
        raise SmokeFailure(
            f"embeddings: expected {EMBEDDING_DIMENSION} dimensions, got {len(vector)}"
        )
    # Nested under extra_fields, not top level. Reading it beside `model` and
    # `usage` raises KeyError instead of failing the assertion it belongs to.
    routing = payload.get("extra_fields", {}).get("routing_info", {})
    if routing.get("provider") != "embark" or routing.get("key") != "embark-cluster":
        raise SmokeFailure(
            f"embeddings: routing_info {routing!r} does not name embark. A 200 "
            "carrying a vector proves nothing about which upstream answered; "
            "this is what proves the private-IP base_url is still reachable."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://192.168.2.50:8080")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    user = vault_field("secret/default/bifrost/credentials", "username")
    password = vault_field("secret/default/bifrost/credentials", "password")
    vk = vault_field("secret/default/hermes/bifrost", "API_KEY")
    if not user or not password or not vk:
        print("could not read Bifrost credentials from Vault", file=sys.stderr)
        return 2

    status, raw = request(f"{base}/api/version")
    version = raw.decode().strip() if status == 200 else "unknown"
    print(f"gateway {version} at {base}")

    checks: tuple[tuple[str, Callable[[], None]], ...] = (
        ("inference auth enforced", partial(assert_inference_auth_enforced, base)),
        (
            "/metrics behind basic auth",
            partial(assert_metrics_behind_basic_auth, base, user, password),
        ),
        (
            "no unauthenticated admin path",
            partial(assert_no_unauthenticated_admin_path, base),
        ),
        (
            "virtual keys survive",
            partial(assert_virtual_keys_survive, base, user, password),
        ),
        ("embeddings reach embark", partial(assert_embeddings_reach_embark, base, vk)),
    )
    for name, check in checks:
        try:
            check()
        except SmokeFailure as exc:
            print(f"FAIL {name}: {exc}", file=sys.stderr)
            return 1
        print(f"ok   {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
