"""`nomad_client` fetchers, against respx -- no real network.

Modeled on `cli/tests/test_api_nomad.py`: parse-shape, token-header
placement, and pagination-follow are the three behaviors Requirement 4
calls out as load-bearing for this copy.
"""

import httpx
import respx

from dash_app.nomad_client import NEXT_TOKEN_HEADER, job_statuses, list_nodes

ADDRESS = "https://nomad.test.invalid"
TOKEN = "a-token"

STATUSES = f"{ADDRESS}/v1/jobs/statuses"
NODES = f"{ADDRESS}/v1/nodes"

ONE_JOB = [
    {
        "Name": "grafana",
        "Type": "service",
        "Status": "running",
        "Stop": False,
        "GroupCountSum": 1,
        "Allocs": [{"ClientStatus": "running", "Group": "grafana", "NodeID": "n1"}],
    }
]

ONE_NODE = [
    {"Name": "firebat", "Status": "ready", "SchedulingEligibility": "eligible", "Drain": False}
]


@respx.mock
def test_job_statuses_parses_the_response_shape() -> None:
    respx.get(STATUSES).mock(return_value=httpx.Response(200, json=ONE_JOB))

    jobs = job_statuses(ADDRESS, TOKEN)

    assert len(jobs) == 1
    assert jobs[0].name == "grafana"
    assert jobs[0].running_allocs == 1


@respx.mock
def test_the_token_is_sent_in_nomads_own_header() -> None:
    route = respx.get(STATUSES).mock(return_value=httpx.Response(200, json=[]))

    job_statuses(ADDRESS, TOKEN)

    assert route.calls.last.request.headers["X-Nomad-Token"] == TOKEN


@respx.mock
def test_pagination_is_followed_until_the_token_is_empty() -> None:
    respx.get(STATUSES).mock(
        side_effect=[
            httpx.Response(200, json=ONE_JOB, headers={NEXT_TOKEN_HEADER: "page-2"}),
            httpx.Response(200, json=ONE_JOB),
        ]
    )

    jobs = job_statuses(ADDRESS, TOKEN)

    assert len(jobs) == 2
    assert len(respx.calls) == 2


@respx.mock
def test_pagination_passes_the_next_token_back() -> None:
    respx.get(STATUSES).mock(
        side_effect=[
            httpx.Response(200, json=[], headers={NEXT_TOKEN_HEADER: "page-2"}),
            httpx.Response(200, json=[]),
        ]
    )

    job_statuses(ADDRESS, TOKEN)

    assert "next_token=page-2" in str(respx.calls[1].request.url)


@respx.mock
def test_list_nodes_parses_the_response_shape() -> None:
    respx.get(NODES).mock(return_value=httpx.Response(200, json=ONE_NODE))

    nodes = list_nodes(ADDRESS, TOKEN)

    assert len(nodes) == 1
    assert nodes[0].usable
