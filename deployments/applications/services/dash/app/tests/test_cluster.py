"""The deployed dash job, over the network.

Marked `cluster` and excluded from the default run. Run on purpose:

    uv run --project deployments/applications/services/dash/app pytest -m cluster

Talks to dash's own address directly (not through oauth2-proxy's edge
gate, which needs an authenticated browser session and is L1's concern,
already covered there) -- the same shape as cli/tests/test_api_live.py's
direct-service reads.
"""

import os

import httpx
import pytest

pytestmark = pytest.mark.cluster

STATUS_VALUES = {"up", "degraded", "down", "unknown"}


def _dash_addr() -> str:
    return os.environ.get("DASH_ADDR", "http://192.168.2.50:8000")


def test_status_endpoint_answers_with_live_tiles() -> None:
    addr = _dash_addr()
    try:
        response = httpx.get(f"{addr}/api/status", timeout=10)
    except httpx.TransportError:
        pytest.skip(f"{addr} unreachable from this host")

    assert response.status_code == 200
    body = response.json()

    assert "tiles" in body
    assert len(body["tiles"]) > 0
    for tile in body["tiles"]:
        assert tile["status"] in STATUS_VALUES
        assert tile["key"]
        assert tile["node"]


def test_a_known_dashboard_tile_reports_a_real_status() -> None:
    """Spot-check one tile the operator can cross-verify by hand.

    grafana is a Nomad-scheduled dashboard tile with a real job -- a
    plausible target to compare against `localstack service grafana` or
    `nomad job status grafana` if this ever needs manual verification.
    """
    addr = _dash_addr()
    try:
        response = httpx.get(f"{addr}/api/status", timeout=10)
    except httpx.TransportError:
        pytest.skip(f"{addr} unreachable from this host")

    body = response.json()
    grafana = next((t for t in body["tiles"] if t["key"] == "grafana"), None)
    if grafana is None:
        pytest.skip("no grafana tile in the deployed tiles.json")

    assert grafana["status"] in STATUS_VALUES
