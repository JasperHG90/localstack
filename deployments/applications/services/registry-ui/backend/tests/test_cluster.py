"""Live-cluster checks. Excluded from the default run by the `cluster` marker."""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.cluster

DEFAULT_ADDR = "https://registry-ui.lab.orangecluster.nl"


def _addr() -> str:
    return os.environ.get("REGISTRY_UI_ADDR", DEFAULT_ADDR).rstrip("/")


def test_the_registry_route_returns_models_from_the_live_registry() -> None:
    """The one case that touches the real registry.

    Every other test here is respx-mocked against fixtures, so this is the
    only place the OCI shapes meet what the cluster actually serves.
    """
    try:
        response = httpx.get(f"{_addr()}/api/registry", timeout=30)
    except httpx.TransportError:
        pytest.skip(f"{_addr()} unreachable from this host")

    assert response.status_code == 200
    body = response.json()
    assert "models" in body
    assert "images" in body
    if body.get("error"):
        pytest.skip(f"registry unreachable from registry-ui: {body['error']}")

    for kit in body["models"]:
        assert kit["repo"]
        assert kit["tags"]
        assert kit["digest"].startswith("sha256:")
        kinds = {layer["kind"] for layer in kit["layers"]}
        assert kinds <= {"model", "modelpart", "code", "docs", "other"}
