"""`consul_client` fetchers, against respx -- no real network.

Modeled on `cli/tests/test_api_nomad.py`'s convention, adapted for Consul's
tokenless reads (`consul_client.py`'s own docstring explains why no token
is sent).
"""

import httpx
import respx

from dash_app.consul_client import list_checks, list_services

ADDRESS = "https://consul.test.invalid"

CHECKS = f"{ADDRESS}/v1/health/state/any"
SERVICES = f"{ADDRESS}/v1/catalog/services"

ONE_CHECK = [
    {"Name": "grafana-http", "Status": "passing", "Node": "firebat", "ServiceName": "grafana"}
]
ONE_CATALOG = {"grafana": ["dashboard"]}


@respx.mock
def test_list_checks_parses_the_response_shape() -> None:
    respx.get(CHECKS).mock(return_value=httpx.Response(200, json=ONE_CHECK))

    checks = list_checks(ADDRESS)

    assert len(checks) == 1
    assert checks[0].service == "grafana"
    assert not checks[0].failing


@respx.mock
def test_no_token_header_is_sent() -> None:
    route = respx.get(CHECKS).mock(return_value=httpx.Response(200, json=[]))

    list_checks(ADDRESS)

    assert not route.calls.last.request.headers.get("X-Consul-Token")


@respx.mock
def test_list_services_maps_names_to_tags() -> None:
    respx.get(SERVICES).mock(return_value=httpx.Response(200, json=ONE_CATALOG))

    catalog = list_services(ADDRESS)

    assert catalog == {"grafana": ["dashboard"]}
