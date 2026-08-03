"""Consul checks: every one fetched, only the failing ones shown."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from localstack_cli.api.consul import failing, list_checks
from localstack_cli.api.errors import MissingCapability, Unreachable

FIXTURES = Path(__file__).parent / "fixtures" / "capture"
ADDRESS = "https://consul.test.invalid"
HEALTH = f"{ADDRESS}/v1/health/state/any"


def payload() -> list[dict[str, object]]:
    loaded: list[dict[str, object]] = json.loads((FIXTURES / "consul_health.json").read_text())
    return loaded


@respx.mock
def test_the_live_capture_parses() -> None:
    respx.get(HEALTH).mock(return_value=httpx.Response(200, json=payload()))

    checks = list_checks(ADDRESS)

    assert len(checks) == 41


@respx.mock
def test_no_token_is_sent() -> None:
    """Tokenless works because the agent's `tokens.default` is its own token."""
    route = respx.get(HEALTH).mock(return_value=httpx.Response(200, json=payload()))

    list_checks(ADDRESS)

    assert "X-Consul-Token" not in route.calls.last.request.headers


@respx.mock
def test_a_healthy_cluster_has_nothing_to_show() -> None:
    respx.get(HEALTH).mock(return_value=httpx.Response(200, json=payload()))

    assert failing(list_checks(ADDRESS)) == []


@respx.mock
def test_only_the_failing_checks_come_back() -> None:
    """Never the wall of 41 passing ones: that buries the two that matter."""
    raw = payload()
    raw[0]["Status"] = "critical"
    raw[1]["Status"] = "warning"
    respx.get(HEALTH).mock(return_value=httpx.Response(200, json=raw))

    shown = failing(list_checks(ADDRESS))

    assert len(shown) == 2
    assert {check.status for check in shown} == {"critical", "warning"}


@respx.mock
def test_a_tightened_acl_degrades_rather_than_crashes() -> None:
    """If `tokens.default` ever goes away, this is the designed behavior."""
    respx.get(HEALTH).mock(return_value=httpx.Response(403, text="Permission denied"))

    with pytest.raises(MissingCapability) as caught:
        list_checks(ADDRESS)

    assert caught.value.capability == "service:read"


@respx.mock
def test_an_unreachable_consul_names_the_address() -> None:
    respx.get(HEALTH).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(Unreachable):
        list_checks(ADDRESS)
