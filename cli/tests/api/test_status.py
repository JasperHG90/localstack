"""Four sources at once, and one failure must not touch the others."""

import json
from pathlib import Path

import httpx
import respx

from localstack_cli.api.status import fetch

FIXTURES = Path(__file__).parent.parent / "fixtures" / "capture"
VAULT = "https://vault.test.invalid"
NOMAD = "https://nomad.test.invalid"
CONSUL = "https://consul.test.invalid"


def payload(name: str) -> object:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def mock_everything_healthy() -> None:
    respx.get(f"{VAULT}/v1/sys/health").mock(
        return_value=httpx.Response(
            200, json={"initialized": True, "sealed": False, "version": "9.9.9"}
        )
    )
    respx.get(f"{NOMAD}/v1/nodes").mock(return_value=httpx.Response(200, json=payload("nodes")))
    respx.get(f"{NOMAD}/v1/jobs/statuses").mock(
        return_value=httpx.Response(200, json=payload("jobs_statuses"))
    )
    respx.get(f"{CONSUL}/v1/health/state/any").mock(
        return_value=httpx.Response(200, json=payload("consul_health"))
    )


@respx.mock
def test_a_healthy_cluster_fills_every_section() -> None:
    mock_everything_healthy()

    result = fetch(VAULT, NOMAD, CONSUL, "a-token")

    assert result.ok
    assert result.failed == []
    assert result.vault.value is not None and not result.vault.value.sealed
    assert result.nodes.value is not None and len(result.nodes.value) == 5
    assert result.jobs.value is not None and len(result.jobs.value) == 19
    assert result.checks.value is not None and len(result.checks.value) == 41


@respx.mock
def test_one_dead_source_does_not_blank_the_others() -> None:
    """Three green panels from a swallowed timeout is the failure guarded."""
    mock_everything_healthy()
    respx.get(f"{CONSUL}/v1/health/state/any").mock(side_effect=httpx.ReadTimeout("slow"))

    result = fetch(VAULT, NOMAD, CONSUL, "a-token", timeout=0.05)

    assert not result.ok
    assert result.failed == ["consul"]
    assert result.vault.ok
    assert result.nodes.ok
    assert result.jobs.ok
    assert result.checks.error is not None
    assert "consul" in result.checks.error


@respx.mock
def test_a_denied_nomad_leaves_vault_and_consul_alone() -> None:
    """The live shape today: the brokered token cannot list jobs."""
    mock_everything_healthy()
    respx.get(f"{NOMAD}/v1/jobs/statuses").mock(
        return_value=httpx.Response(403, text="Permission denied")
    )
    respx.get(f"{NOMAD}/v1/nodes").mock(return_value=httpx.Response(403, text="Permission denied"))

    result = fetch(VAULT, NOMAD, CONSUL, "a-token")

    assert result.failed == ["nodes", "jobs"]
    assert result.vault.ok
    assert result.checks.ok
    assert result.jobs.error is not None and "list-jobs" in result.jobs.error


@respx.mock
def test_an_unclassified_error_is_contained_too() -> None:
    """An exception the fetch layer never mapped must not kill three sections."""
    mock_everything_healthy()
    respx.get(f"{VAULT}/v1/sys/health").mock(side_effect=ValueError("something odd"))

    result = fetch(VAULT, NOMAD, CONSUL, "a-token")

    assert result.failed == ["vault"]
    assert result.vault.error is not None and "something odd" in result.vault.error
    assert result.nodes.ok and result.jobs.ok and result.checks.ok


@respx.mock
def test_vault_answers_without_a_token() -> None:
    """`sys/health` is the section that works when the session is dead."""
    mock_everything_healthy()

    result = fetch(VAULT, NOMAD, CONSUL, None)

    assert result.vault.ok
    # Found by URL, not by index: the four fetches are concurrent, so the
    # call order is not fixed and indexing would flake.
    health = next(call.request for call in respx.calls if call.request.url.path == "/v1/sys/health")
    assert "X-Vault-Token" not in health.headers
