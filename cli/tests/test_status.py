import json

import pytest

from localstack_cli.config import CONSUL_HTTP_ADDR, NOMAD_ADDR, VAULT_ADDR
from localstack_cli.status import probe_cluster, probe_identity
from tests.fixtures.cluster import LOOKUP_SELF, FakeCluster


@pytest.fixture
def pointed_at_cluster(monkeypatch: pytest.MonkeyPatch, cluster_addr: str) -> None:
    for name in (VAULT_ADDR, NOMAD_ADDR, CONSUL_HTTP_ADDR):
        monkeypatch.setenv(name, cluster_addr)


def test_all_three_probes_are_green_against_a_healthy_cluster(
    pointed_at_cluster: None,
) -> None:
    status = probe_cluster()
    assert [(p.name, p.ok) for p in status.probes] == [
        ("vault", True),
        ("nomad", True),
        ("consul", True),
    ]


def test_probes_are_red_when_nothing_is_listening() -> None:
    # The autouse fixture already points every address at a closed port.
    status = probe_cluster()
    assert [p.ok for p in status.probes] == [False, False, False]
    assert all(p.detail for p in status.probes), "a red dot must say why"


def test_a_sealed_vault_is_red_and_says_so(pointed_at_cluster: None, cluster: FakeCluster) -> None:
    """503 is the case a naive `status == 200` check would call unreachable.

    Vault answering at all proves the address is right, so the distinction
    between sealed and unreachable is the useful part of the probe.
    """
    cluster.routes["/v1/sys/health"] = (503, b'{"sealed":true}')
    vault = next(p for p in probe_cluster().probes if p.name == "vault")
    assert (vault.ok, vault.detail) == (False, "sealed")


def test_a_standby_vault_is_green(pointed_at_cluster: None, cluster: FakeCluster) -> None:
    cluster.routes["/v1/sys/health"] = (429, b'{"standby":true}')
    vault = next(p for p in probe_cluster().probes if p.name == "vault")
    assert vault.ok


def test_consul_without_a_leader_is_red(pointed_at_cluster: None, cluster: FakeCluster) -> None:
    """Consul answers 200 with an empty leader mid-election."""
    cluster.routes["/v1/status/leader"] = (200, b'""')
    consul = next(p for p in probe_cluster().probes if p.name == "consul")
    assert (consul.ok, consul.detail) == (False, "no leader")


def test_consul_reports_the_leader_address(pointed_at_cluster: None) -> None:
    consul = next(p for p in probe_cluster().probes if p.name == "consul")
    assert consul.detail == "leader 192.168.2.30:8300"


def test_missing_addresses_yield_no_probes_and_name_the_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(VAULT_ADDR)
    status = probe_cluster()
    assert status.probes == ()
    assert VAULT_ADDR in status.identity.detail


def test_identity_is_green_and_names_the_user(cluster_addr: str) -> None:
    identity = probe_identity(cluster_addr, "a-token")
    assert identity.logged_in
    assert identity.detail.startswith("jasper (")


def test_identity_reports_the_remaining_ttl(cluster_addr: str) -> None:
    # 27000s is 7h30m, so the formatting is visible rather than rounded away.
    assert probe_identity(cluster_addr, "a-token").detail == "jasper (7h30m left)"


def test_identity_falls_back_to_display_name_without_metadata(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    payload = {"data": {"display_name": "token", "ttl": 0}}
    cluster.routes["/v1/auth/token/lookup-self"] = (200, json.dumps(payload).encode())
    assert probe_identity(cluster_addr, "a-token").detail == "token (does not expire)"


def test_identity_without_a_token_says_how_to_fix_it(closed_addr: str) -> None:
    identity = probe_identity(closed_addr, None)
    assert not identity.logged_in
    assert "localstack login" in identity.detail


def test_a_revoked_token_is_red(cluster_addr: str, cluster: FakeCluster) -> None:
    cluster.routes["/v1/auth/token/lookup-self"] = (403, b'{"errors":["permission"]}')
    identity = probe_identity(cluster_addr, "stale")
    assert (identity.logged_in, identity.detail) == (
        False,
        "token expired or revoked",
    )


def test_a_token_with_an_unreachable_vault_is_reported_separately(
    closed_addr: str,
) -> None:
    """Having a token and having a cluster are different failures."""
    identity = probe_identity(closed_addr, "a-token")
    assert not identity.logged_in
    assert "token present" in identity.detail


def test_the_probe_sends_the_token_as_a_vault_header(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """Without the header Vault would answer 403, so this proves the probe
    authenticates rather than getting lucky against a permissive fake."""
    assert LOOKUP_SELF["data"]["meta"] == {"username": "jasper"}
    cluster.routes["/v1/auth/token/lookup-self"] = (403, b"{}")
    assert not probe_identity(cluster_addr, "a-token").logged_in
