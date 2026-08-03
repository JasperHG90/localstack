"""Nomad fetchers, against the captured payload shapes over respx."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from localstack_cli.api.errors import MissingCapability, NotAuthenticated, Timeout, Unreachable
from localstack_cli.api.nomad import MAX_PAGES, NEXT_TOKEN_HEADER, job_statuses, list_nodes

FIXTURES = Path(__file__).parent / "fixtures" / "capture"
ADDRESS = "https://nomad.test.invalid"
TOKEN = "a-token"

STATUSES = f"{ADDRESS}/v1/jobs/statuses"
NODES = f"{ADDRESS}/v1/nodes"


def payload(name: str) -> list[dict[str, object]]:
    loaded: list[dict[str, object]] = json.loads((FIXTURES / f"{name}.json").read_text())
    return loaded


@respx.mock
def test_job_statuses_parses_the_live_capture() -> None:
    respx.get(STATUSES).mock(return_value=httpx.Response(200, json=payload("jobs_statuses")))

    jobs = job_statuses(ADDRESS, TOKEN)

    assert len(jobs) == 19
    assert {job.name for job in jobs} >= {"talat-shim", "acme", "node-exporter"}


@respx.mock
def test_the_token_is_sent_in_nomads_own_header() -> None:
    route = respx.get(STATUSES).mock(return_value=httpx.Response(200, json=[]))

    job_statuses(ADDRESS, TOKEN)

    assert route.calls.last.request.headers["X-Nomad-Token"] == TOKEN


@respx.mock
def test_pagination_is_followed() -> None:
    """A single-page implementation under-reports and fails here."""
    first = payload("jobs_statuses")[:5]
    second = payload("jobs_statuses")[5:]
    respx.get(STATUSES).mock(
        side_effect=[
            httpx.Response(200, json=first, headers={NEXT_TOKEN_HEADER: "page-2"}),
            httpx.Response(200, json=second),
        ]
    )

    jobs = job_statuses(ADDRESS, TOKEN)

    assert len(jobs) == 19


@respx.mock
def test_pagination_passes_the_token_back() -> None:
    respx.get(STATUSES).mock(
        side_effect=[
            httpx.Response(200, json=[], headers={NEXT_TOKEN_HEADER: "page-2"}),
            httpx.Response(200, json=[]),
        ]
    )

    job_statuses(ADDRESS, TOKEN)

    assert "next_token=page-2" in str(respx.calls[1].request.url)


@respx.mock
def test_a_policy_gap_names_the_capability() -> None:
    respx.get(STATUSES).mock(return_value=httpx.Response(403, text="Permission denied"))

    with pytest.raises(MissingCapability) as caught:
        job_statuses(ADDRESS, TOKEN)

    assert caught.value.capability == "list-jobs"
    assert "list-jobs" in str(caught.value)


@respx.mock
def test_a_dead_token_is_not_a_policy_gap() -> None:
    """Conflating them sends someone to re-login over a policy gap."""
    respx.get(STATUSES).mock(return_value=httpx.Response(403, text="ACL token not found"))

    with pytest.raises(NotAuthenticated) as caught:
        job_statuses(ADDRESS, TOKEN)

    assert "localstack login" in str(caught.value)


@respx.mock
def test_a_refused_connection_is_unreachable() -> None:
    respx.get(STATUSES).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(Unreachable) as caught:
        job_statuses(ADDRESS, TOKEN)

    assert ADDRESS in str(caught.value)


@respx.mock
def test_a_slow_source_times_out() -> None:
    respx.get(STATUSES).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(Timeout):
        job_statuses(ADDRESS, TOKEN, timeout=0.01)


@respx.mock
def test_list_nodes_parses_the_live_capture() -> None:
    respx.get(NODES).mock(return_value=httpx.Response(200, json=payload("nodes")))

    nodes = list_nodes(ADDRESS, TOKEN)

    assert len(nodes) == 5
    assert all(node.usable for node in nodes)
    assert {node.name for node in nodes} >= {"firebat", "jetson-orin-nano"}


@respx.mock
def test_nodes_name_their_own_capability_on_denial() -> None:
    respx.get(NODES).mock(return_value=httpx.Response(403, text="Permission denied"))

    with pytest.raises(MissingCapability) as caught:
        list_nodes(ADDRESS, TOKEN)

    assert caught.value.capability == "node:read"


@respx.mock
def test_a_draining_node_is_not_usable() -> None:
    raw = payload("nodes")
    raw[0]["Drain"] = True
    respx.get(NODES).mock(return_value=httpx.Response(200, json=raw))

    nodes = list_nodes(ADDRESS, TOKEN)

    assert sum(1 for node in nodes if node.usable) == 4


@respx.mock
def test_the_job_widget_is_one_call_with_no_per_job_fan_out() -> None:
    """Eval row 5, asserted rather than assumed.

    `/v1/jobs` carries no desired count, so a panel built on it needs a
    `/v1/job/<id>` read per job: 19 extra calls every 5 seconds here, which
    also falsifies the "negligible load" claim behind the refresh interval.
    """
    respx.get(STATUSES).mock(return_value=httpx.Response(200, json=payload("jobs_statuses")))

    job_statuses(ADDRESS, TOKEN)

    paths = [request.url.path for request in (call.request for call in respx.calls)]
    assert paths == ["/v1/jobs/statuses"]


@respx.mock
def test_pagination_costs_only_its_continuations() -> None:
    respx.get(STATUSES).mock(
        side_effect=[
            httpx.Response(200, json=[], headers={NEXT_TOKEN_HEADER: "page-2"}),
            httpx.Response(200, json=[]),
        ]
    )

    job_statuses(ADDRESS, TOKEN)

    assert len(respx.calls) == 2


@respx.mock
def test_a_server_that_always_pages_does_not_spin_forever() -> None:
    """A refresh must finish, even against a misbehaving endpoint."""
    respx.get(STATUSES).mock(
        return_value=httpx.Response(200, json=[], headers={NEXT_TOKEN_HEADER: "always"})
    )

    job_statuses(ADDRESS, TOKEN)

    assert len(respx.calls) == MAX_PAGES
