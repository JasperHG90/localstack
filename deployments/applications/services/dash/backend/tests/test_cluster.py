"""The deployed dash backend task, over the network.

Marked `cluster` and excluded from the default run. Run on purpose:

    uv run --project deployments/applications/services/dash/backend pytest -m cluster

Talks to the backend task's own port directly (not through oauth2-proxy's
edge gate, which needs an authenticated browser session and is L1's
concern, already covered there) -- the same shape as
cli/tests/test_api_live.py's direct-service reads. Since the frontend/
backend split (L4), `/api/status` answers on the backend task's own port,
not the frontend's.

Excluded from the default run by `addopts` in pyproject.toml, so nothing
in the commit gate covers these two. They are run on purpose, after a
deploy.
"""

import os
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.cluster

STATUS_VALUES = {"up", "degraded", "down", "unknown"}


def _dash_addr() -> str:
    return os.environ.get("DASH_ADDR", "http://192.168.2.50:8001")


def _tiles(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [tile for group in body["groups"] for tile in group["tiles"]]


def test_status_endpoint_answers_with_live_groups() -> None:
    addr = _dash_addr()
    try:
        response = httpx.get(f"{addr}/api/status", timeout=10)
    except httpx.TransportError:
        pytest.skip(f"{addr} unreachable from this host")

    assert response.status_code == 200
    body = response.json()

    assert "groups" in body
    assert len(body["groups"]) > 0
    for group in body["groups"]:
        assert group["key"]
        assert group["title"]
        assert len(group["tiles"]) > 0

    for tile in _tiles(body):
        assert tile["status"] in STATUS_VALUES
        assert tile["key"]
        assert tile["node"]
        assert tile["jobs"]
        for job in tile["jobs"]:
            assert job["name"]
            assert job["node"]
            assert job["status"] in STATUS_VALUES


def test_a_known_tile_reports_a_real_status() -> None:
    """Spot-check one tile the operator can cross-verify by hand.

    grafana is a Nomad-scheduled job with a browser UI -- a plausible
    target to compare against `localstack service grafana` or `nomad job
    status grafana` if this ever needs manual verification.
    """
    addr = _dash_addr()
    try:
        response = httpx.get(f"{addr}/api/status", timeout=10)
    except httpx.TransportError:
        pytest.skip(f"{addr} unreachable from this host")

    body = response.json()
    grafana = next((t for t in _tiles(body) if t["key"] == "grafana"), None)
    if grafana is None:
        pytest.skip("no grafana tile in the deployed tiles.json")

    assert grafana["status"] in STATUS_VALUES
