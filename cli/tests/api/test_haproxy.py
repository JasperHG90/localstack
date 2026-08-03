"""The edge routing parser, and the credential it must never let out."""

import json
from dataclasses import asdict

import pytest

from localstack_cli.api.haproxy import HaproxyParseError, parse_routes
from tests.fixtures.haproxy_cfg import FAKE_PASSWORD, LIVE_SHAPE, MALFORMED

LEAK_MARKERS = (FAKE_PASSWORD, "insecure-password", "openfang_users")


def test_every_live_route_is_parsed() -> None:
    routes = parse_routes(LIVE_SHAPE)

    assert len(routes) == 10
    assert {route.name for route in routes} == {
        "minio",
        "s3",
        "vault",
        "nomad",
        "consul",
        "phoenix",
        "memex",
        "grafana",
        "mlflow",
        "bifrost",
    }


def test_a_route_carries_its_hostname_and_backend() -> None:
    routes = {route.name: route for route in parse_routes(LIVE_SHAPE)}

    assert routes["s3"].hostname == "s3.lab.example"
    assert routes["s3"].backend_host == "10.0.0.29"
    assert routes["s3"].backend_port == 9000
    assert routes["s3"].url == "https://s3.lab.example"


def test_an_authenticated_backend_still_parses() -> None:
    """`phoenix` and `mlflow` carry an `http-request auth` line first."""
    routes = {route.name: route for route in parse_routes(LIVE_SHAPE)}

    assert routes["phoenix"].backend_port == 6006
    assert routes["mlflow"].backend_port == 5000


def test_the_stats_frontend_is_not_a_route() -> None:
    """It has a `bind` but no ACL, so it must not become a row."""
    assert "stats" not in {route.name for route in parse_routes(LIVE_SHAPE)}


def test_no_credential_reaches_a_dataclass() -> None:
    """The parser copies four fields out and touches nothing else."""
    routes = parse_routes(LIVE_SHAPE)

    rendered = json.dumps([asdict(route) for route in routes])
    for marker in LEAK_MARKERS:
        assert marker not in rendered


def test_no_credential_reaches_a_repr() -> None:
    """`repr()` is what a debugger, a log line and a pytest failure print."""
    rendered = repr(parse_routes(LIVE_SHAPE))

    for marker in LEAK_MARKERS:
        assert marker not in rendered


def test_no_credential_reaches_an_exception() -> None:
    """The error path is the one that gets forgotten.

    A parser that quotes the config it failed on prints the password that
    config contains, and it does so in a traceback that lands in a terminal
    scrollback or a CI log.
    """
    with pytest.raises(HaproxyParseError) as caught:
        parse_routes("nothing that looks like a config")

    for marker in LEAK_MARKERS:
        assert marker not in str(caught.value)


def test_a_malformed_config_carrying_the_credential_does_not_leak_it() -> None:
    """The same, against input that actually holds the secret."""
    try:
        routes = parse_routes(MALFORMED)
    except HaproxyParseError as error:
        for marker in LEAK_MARKERS:
            assert marker not in str(error)
        return

    # Parsed without raising: then nothing may have come through either.
    rendered = json.dumps([asdict(route) for route in routes])
    for marker in LEAK_MARKERS:
        assert marker not in rendered


def test_a_route_without_a_backend_is_dropped_not_half_rendered() -> None:
    config = LIVE_SHAPE.replace("backend s3\n    server s3_1 10.0.0.29:9000 check\n", "")

    routes = {route.name for route in parse_routes(config)}

    assert "s3" not in routes
    assert len(routes) == 9


def test_the_parser_returns_nothing_that_holds_the_input() -> None:
    """No field anywhere may carry config text."""
    for route in parse_routes(LIVE_SHAPE):
        for value in asdict(route).values():
            assert "\n" not in str(value)


def test_the_parse_error_is_catchable_by_the_command_layer() -> None:
    """A bare RuntimeError would escape to typer and print a traceback whose
    frames still hold the template text.
    """
    from localstack_cli.api.errors import ClusterError

    with pytest.raises(ClusterError):
        parse_routes("nothing that looks like a config")


def test_tracebacks_never_render_local_variables() -> None:
    """Requirement 8's last mile, stated rather than inherited from typer."""
    from localstack_cli.main import app as cli

    assert cli.pretty_exceptions_show_locals is False
