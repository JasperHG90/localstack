"""`localstack token <svc>`: the stdout contract D6's PATH shims depend on.

The shim does `T="$(localstack token nomad)"` and puts `$T` straight into
`NOMAD_TOKEN`, so these assert on stdout byte for byte rather than with `in`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from localstack_cli.auth.session import Credential, Session, save, session_path
from localstack_cli.main import app
from tests.fixtures.cluster import FakeCluster

runner = CliRunner()


@pytest.fixture
def logged_in(cluster_addr: str) -> Session:
    now = datetime.now(UTC)
    session = Session(
        method="userpass",
        vault_addr=cluster_addr,
        username="operator",
        vault=Credential("hvs.vault", "va", now + timedelta(days=30), True),
        nomad=Credential("nomad-tok", "na", now + timedelta(minutes=25), True),
        consul=Credential("consul-tok", "ca", now + timedelta(minutes=25), True),
    )
    save(session, session_path())
    return session


@pytest.mark.parametrize(
    ("service", "expected"),
    [("vault", "hvs.vault"), ("nomad", "nomad-tok"), ("consul", "consul-tok")],
)
def test_stdout_is_the_token_and_one_newline(
    logged_in: Session, service: str, expected: str
) -> None:
    """Byte for byte. One stray character becomes an invalid token and a 403
    that reads like a permissions bug."""
    result = runner.invoke(app, ["token", service])
    assert result.exit_code == 0
    assert result.stdout == expected + "\n"


def test_no_session_fails_closed_with_empty_stdout() -> None:
    """The shim's fall-through to the bare binary is only safe because a
    failure produces nothing to export."""
    result = runner.invoke(app, ["token", "nomad"])
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "localstack login" in result.stderr


def test_a_denied_broker_fails_closed_with_empty_stdout(
    logged_in: Session, cluster: FakeCluster
) -> None:
    cluster.routes["/v1/nomad/creds/deploy"] = (403, b'{"errors":["denied"]}')
    # Force the refresh by expiring the cached entry.
    now = datetime.now(UTC)
    save(
        Session(
            method=logged_in.method,
            vault_addr=logged_in.vault_addr,
            username=logged_in.username,
            vault=logged_in.vault,
            nomad=Credential("stale", "na", now - timedelta(minutes=1), True),
            consul=logged_in.consul,
        ),
        session_path(),
    )
    result = runner.invoke(app, ["token", "nomad"])
    assert result.exit_code != 0
    assert result.stdout == ""


def test_an_unknown_service_fails_closed_with_empty_stdout(logged_in: Session) -> None:
    result = runner.invoke(app, ["token", "postgres"])
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "postgres" in result.stderr


def test_a_stale_token_is_refreshed_before_printing(
    logged_in: Session, cluster: FakeCluster
) -> None:
    now = datetime.now(UTC)
    save(
        Session(
            method=logged_in.method,
            vault_addr=logged_in.vault_addr,
            username=logged_in.username,
            vault=logged_in.vault,
            nomad=Credential("stale", "na", now + timedelta(minutes=1), True),
            consul=logged_in.consul,
        ),
        session_path(),
    )
    result = runner.invoke(app, ["token", "nomad"])
    assert result.exit_code == 0
    assert result.stdout == "nomad-secret-id\n"


def test_the_banner_never_reaches_this_command(logged_in: Session) -> None:
    """The root callback returns early for subcommands. If it ever stopped
    doing so, the banner would land on stdout and every shim would break."""
    result = runner.invoke(app, ["token", "vault"])
    assert "LOCALSTACK" not in result.stdout
