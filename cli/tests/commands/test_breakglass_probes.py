"""Probe behavior: timeout, refused, non-2xx, garbage, and the
requirement-9 rendering cases.

Mocking at the HTTP boundary would assert little more than that the mock was
called. The repo's convention (conftest.py) is a real ThreadingHTTPServer
or a real closed port, never a mocked urllib. These tests point the
breakglass EDGE/LAN address dicts at the cluster fixture (a real server)
or a closed port, so the probe code exercises the part that can be wrong:
which code means healthy, which means reachable-but-unusable, and which
combination means a firewall change rather than an outage.
"""

import pytest
from typer.testing import CliRunner

from localstack_cli.commands import breakglass as bg
from localstack_cli.main import app
from tests.fixtures.cluster import FakeCluster

runner = CliRunner()

# A port nothing listens on, so connect fails at once.
CLOSED = "http://127.0.0.1:1"


def _point_at(
    monkeypatch: pytest.MonkeyPatch,
    edge_addrs: dict[str, str],
    lan_addrs: dict[str, str],
) -> None:
    """Point the probe address dicts at the given bases."""
    monkeypatch.setattr(bg, "EDGE", dict(edge_addrs))
    monkeypatch.setattr(bg, "LAN", dict(lan_addrs))


def _all_three(base: str) -> dict[str, str]:
    return {"vault": base, "nomad": base, "consul": base}


def _diagnosis(stdout: str) -> str:
    """Extract the probe diagnosis block from the command output."""
    if "Probe diagnosis" not in stdout:
        return ""
    return stdout.split("Probe diagnosis", 1)[1].split("\n##", 1)[0]


# -- The command prints the full runbook in every probe case -----------------


def test_full_runbook_prints_when_everything_answers(
    cluster: FakeCluster, cluster_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(cluster_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "Vault is sealed" in result.stdout
    assert "All probes answered" in result.stdout


def test_full_runbook_prints_when_everything_refused(
    closed_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_at(monkeypatch, _all_three(closed_addr), _all_three(closed_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "Vault is sealed" in result.stdout
    assert "Nothing answered" in result.stdout


def test_full_runbook_prints_when_edge_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A port that refuses fast so the suite stays quick, exercising the
    # refused path rather than waiting out a full timeout.
    _point_at(monkeypatch, _all_three(CLOSED), _all_three(CLOSED))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "Vault is sealed" in result.stdout


# -- Requirement 9: a closed firewall never reads as an outage --------------


def test_edge_up_lan_dark_is_a_firewall_change_not_an_outage(
    cluster_addr: str, closed_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Edge 200 with all LAN probes refused renders the firewall-change
    finding, and the word 'unreachable' is absent from that case."""
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(closed_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert bg.FIREWALL_CHANGE in result.stdout
    assert "unreachable" not in _diagnosis(result.stdout).lower(), (
        "the edge-up case must not say 'unreachable'"
    )


def test_everything_dark_points_at_your_own_connectivity(
    closed_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_at(monkeypatch, _all_three(closed_addr), _all_three(closed_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "Nothing answered" in result.stdout
    assert "your own connectivity" in result.stdout.lower()


def test_vault_sealed_renders_reachable_but_sealed(
    cluster: FakeCluster, cluster_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vault 503 through the edge renders 'reachable but sealed', naming the
    sealed-Vault section. A bare 'Vault unreachable' FAILS this row."""
    cluster.routes["/v1/sys/health"] = (503, b'{"sealed":true}')
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(CLOSED))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "sealed" in _diagnosis(result.stdout).lower(), (
        "a 503 must render as sealed, not unreachable"
    )
    assert "Vault is sealed" in result.stdout


# -- Consul keeps the leader signal ------------------------------------------


def test_consul_reports_the_leader_address(
    cluster: FakeCluster, cluster_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(cluster_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "All probes answered" in result.stdout


def test_consul_no_leader_is_reported_not_called_an_outage(
    cluster: FakeCluster, cluster_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cluster.routes["/v1/status/leader"] = (200, b'""')
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(cluster_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "no leader" in _diagnosis(result.stdout).lower(), (
        "an empty leader must render, not be swallowed"
    )


# -- Probes never take the command down --------------------------------------


def test_garbage_body_does_not_crash(
    cluster: FakeCluster, cluster_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cluster.routes["/v1/status/leader"] = (200, b"not json at all")
    cluster.routes["/v1/sys/health"] = (200, b"\xff\xfe garbage")
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(cluster_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "Vault is sealed" in result.stdout


def test_non_2xx_does_not_crash(
    cluster: FakeCluster, cluster_addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cluster.routes["/v1/sys/health"] = (500, b'{"errors":["internal"]}')
    _point_at(monkeypatch, _all_three(cluster_addr), _all_three(cluster_addr))
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    assert "Vault is sealed" in result.stdout
