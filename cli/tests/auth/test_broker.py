"""Brokering: the two response shapes, the refresh policy, and the 403 message."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from localstack_cli.auth.broker import (
    BrokerError,
    broker,
    credential_from_login,
    ensure_fresh,
)
from localstack_cli.auth.session import Credential, Session
from tests.fixtures.cluster import LOGIN_RESPONSE, FakeCluster

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def session_at(
    cluster_addr: str,
    nomad_minutes: int,
    consul_minutes: int,
    nomad_manage_minutes: int = 30,
) -> Session:
    return Session(
        method="userpass",
        vault_addr=cluster_addr,
        username="operator",
        vault=Credential(
            token="hvs.session-token",
            accessor="vault-accessor",
            expires_at=NOW + timedelta(days=30),
            renewable=True,
        ),
        nomad=Credential(
            token="old-nomad",
            accessor="old-nomad-accessor",
            expires_at=NOW + timedelta(minutes=nomad_minutes),
            renewable=True,
        ),
        nomad_manage=Credential(
            token="old-nomad-manage",
            accessor="old-nomad-manage-accessor",
            expires_at=NOW + timedelta(minutes=nomad_manage_minutes),
            renewable=True,
        ),
        consul=Credential(
            token="old-consul",
            accessor="old-consul-accessor",
            expires_at=NOW + timedelta(minutes=consul_minutes),
            renewable=True,
        ),
    )


def test_the_two_engines_use_different_field_names(cluster_addr: str) -> None:
    """Measured on the live cluster: nomad returns `secret_id`/`accessor_id`
    and consul returns `token`/`accessor`. Reading the wrong one yields an
    empty token and a 403 that looks like a permissions problem."""
    nomad = broker("nomad", cluster_addr, "hvs.session-token", NOW)
    consul = broker("consul", cluster_addr, "hvs.session-token", NOW)
    assert (nomad.token, nomad.accessor) == ("nomad-secret-id", "nomad-accessor-id")
    assert (consul.token, consul.accessor) == ("consul-token", "consul-accessor")


def test_manage_creds_broker_from_the_manage_path(cluster_addr: str) -> None:
    """`nomad/creds/manage` is a separate role on the same Nomad secrets
    engine as `deploy`, so it shares the engine's field names."""
    manage = broker("nomad_manage", cluster_addr, "hvs.session-token", NOW)
    assert (manage.token, manage.accessor) == ("nomad-manage-secret-id", "nomad-manage-accessor-id")


def test_the_lease_becomes_an_absolute_expiry(cluster_addr: str) -> None:
    nomad = broker("nomad", cluster_addr, "hvs.session-token", NOW)
    assert nomad.expires_at == NOW + timedelta(seconds=1800)
    assert nomad.renewable is True
    assert nomad.lease_id.startswith("nomad/creds/deploy/")


def test_brokering_authenticates_with_the_session_token(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    broker("nomad", cluster_addr, "hvs.session-token", NOW)
    assert cluster.requests_for("/v1/nomad/creds/deploy")[0].token == "hvs.session-token"


def test_an_unknown_service_is_refused(cluster_addr: str) -> None:
    with pytest.raises(BrokerError, match="unknown service"):
        broker("postgres", cluster_addr, "hvs.session-token", NOW)


def test_a_403_names_the_path_the_policies_and_the_ticket(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """The message a developer sees when the grant is missing, so it gets the
    most care. It must report `identity_policies`, not `policies`."""
    cluster.routes["/v1/nomad/creds/deploy"] = (
        403,
        json.dumps({"errors": ["1 error occurred: permission denied"]}).encode(),
    )
    with pytest.raises(BrokerError) as caught:
        broker("nomad", cluster_addr, "hvs.session-token", NOW)
    message = str(caught.value)
    assert "nomad/creds/deploy" in message
    assert "developer" in message, "must report identity_policies, not just policies"
    assert "F11" in message


def test_a_403_on_manage_names_the_manage_path(cluster_addr: str, cluster: FakeCluster) -> None:
    cluster.routes["/v1/nomad/creds/manage"] = (
        403,
        json.dumps({"errors": ["1 error occurred: permission denied"]}).encode(),
    )
    with pytest.raises(BrokerError) as caught:
        broker("nomad_manage", cluster_addr, "hvs.session-token", NOW)
    message = str(caught.value)
    assert "nomad/creds/manage" in message
    assert "developer" in message, "must report identity_policies, not just policies"


def test_a_403_still_reports_when_the_policy_lookup_also_fails(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """The lookup is a courtesy; losing it must not replace the 403 with a
    less useful error about the lookup."""
    cluster.routes["/v1/nomad/creds/deploy"] = (403, b'{"errors":["denied"]}')
    cluster.routes["/v1/auth/token/lookup-self"] = (403, b'{"errors":["denied"]}')
    with pytest.raises(BrokerError, match="nomad/creds/deploy"):
        broker("nomad", cluster_addr, "hvs.session-token", NOW)


def test_a_changed_response_shape_is_reported_not_silently_empty(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    cluster.routes["/v1/nomad/creds/deploy"] = (
        200,
        json.dumps({"lease_duration": 1800, "data": {"wrong": "shape"}}).encode(),
    )
    with pytest.raises(BrokerError, match="secret_id"):
        broker("nomad", cluster_addr, "hvs.session-token", NOW)


def test_credential_from_login_maps_the_auth_block() -> None:
    entry = credential_from_login(dict(LOGIN_RESPONSE["auth"]), NOW)
    assert entry.token == "hvs.session-token"
    assert entry.entity_id == "351f302a"
    assert entry.expires_at == NOW + timedelta(seconds=2764800)


def test_the_stored_policies_include_the_group_granted_one() -> None:
    """`token_policies` alone is `['default']` here, because F2 sets
    `token_policies = []` and F11 grants through an identity group. Storing
    that would make `whoami` tell a developer they hold nothing."""
    entry = credential_from_login(dict(LOGIN_RESPONSE["auth"]), NOW)
    assert entry.policies == ("default", "developer")


def test_ensure_fresh_leaves_fresh_credentials_alone(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """Asserts the request was never MADE, by counting what the server saw.

    A loose "not called" assertion would pass against code that re-brokered
    and threw the result away.
    """
    session = session_at(cluster_addr, nomad_minutes=30, consul_minutes=30)
    updated, changed = ensure_fresh(session, NOW)
    assert changed is False
    assert cluster.requests_for("/v1/nomad/creds/deploy") == []
    assert cluster.requests_for("/v1/consul/creds/deploy") == []
    assert updated.nomad is not None and updated.nomad.token == "old-nomad"


def test_ensure_fresh_rebrokers_only_the_stale_one(cluster_addr: str, cluster: FakeCluster) -> None:
    session = session_at(cluster_addr, nomad_minutes=2, consul_minutes=30)
    updated, changed = ensure_fresh(session, NOW)
    assert changed is True
    assert len(cluster.requests_for("/v1/nomad/creds/deploy")) == 1
    assert cluster.requests_for("/v1/consul/creds/deploy") == []
    assert updated.nomad is not None and updated.nomad.token == "nomad-secret-id"
    assert updated.consul is not None and updated.consul.token == "old-consul"


def test_ensure_fresh_rebrokers_manage_independently(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    session = session_at(cluster_addr, nomad_minutes=30, consul_minutes=30, nomad_manage_minutes=2)
    updated, changed = ensure_fresh(session, NOW)
    assert changed is True
    assert cluster.requests_for("/v1/nomad/creds/deploy") == []
    assert len(cluster.requests_for("/v1/nomad/creds/manage")) == 1
    assert cluster.requests_for("/v1/consul/creds/deploy") == []
    assert updated.nomad is not None and updated.nomad.token == "old-nomad"
    assert updated.nomad_manage is not None
    assert updated.nomad_manage.token == "nomad-manage-secret-id"


def test_brokered_credentials_are_rebrokered_never_renewed(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """They cap at `max_ttl 3600`, so renewing buys one window and then fails.
    Re-brokering is unbounded, which is why the policy differs from the Vault
    token's."""
    session = session_at(cluster_addr, nomad_minutes=1, consul_minutes=1)
    ensure_fresh(session, NOW)
    assert cluster.requests_for("/v1/auth/token/renew-self") == []


def test_a_stale_vault_token_is_renewed_not_rebrokered(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    session = session_at(cluster_addr, nomad_minutes=30, consul_minutes=30)
    session = Session(
        method=session.method,
        vault_addr=session.vault_addr,
        username=session.username,
        vault=Credential(
            token="hvs.session-token",
            accessor="vault-accessor",
            expires_at=NOW + timedelta(minutes=1),
            renewable=True,
        ),
        nomad=session.nomad,
        consul=session.consul,
    )
    updated, changed = ensure_fresh(session, NOW)
    assert changed is True
    assert len(cluster.requests_for("/v1/auth/token/renew-self")) == 1
    assert updated.vault.expires_at == NOW + timedelta(seconds=2764800)


def test_an_unrenewable_expired_session_says_to_log_in_again(cluster_addr: str) -> None:
    session = session_at(cluster_addr, nomad_minutes=30, consul_minutes=30)
    session = Session(
        method=session.method,
        vault_addr=session.vault_addr,
        username=session.username,
        vault=Credential(
            token="hvs.session-token",
            accessor="vault-accessor",
            expires_at=NOW - timedelta(minutes=1),
            renewable=False,
        ),
        nomad=session.nomad,
        consul=session.consul,
    )
    with pytest.raises(BrokerError, match="localstack login"):
        ensure_fresh(session, NOW)


def test_a_failed_renewal_says_to_log_in_again(cluster_addr: str, cluster: FakeCluster) -> None:
    """Never silently re-prompt for a password."""
    cluster.routes["/v1/auth/token/renew-self"] = (403, b'{"errors":["denied"]}')
    session = session_at(cluster_addr, nomad_minutes=30, consul_minutes=30)
    session = Session(
        method=session.method,
        vault_addr=session.vault_addr,
        username=session.username,
        vault=Credential(
            token="hvs.session-token",
            accessor="vault-accessor",
            expires_at=NOW + timedelta(minutes=1),
            renewable=True,
        ),
        nomad=session.nomad,
        consul=session.consul,
    )
    with pytest.raises(BrokerError, match="localstack login"):
        ensure_fresh(session, NOW)


def test_a_session_with_no_brokered_pair_brokers_them(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    session = Session(
        method="userpass",
        vault_addr=cluster_addr,
        username="operator",
        vault=Credential(
            token="hvs.session-token",
            accessor="vault-accessor",
            expires_at=NOW + timedelta(days=30),
            renewable=True,
        ),
    )
    updated, changed = ensure_fresh(session, NOW)
    assert changed is True
    assert updated.nomad is not None and updated.consul is not None
