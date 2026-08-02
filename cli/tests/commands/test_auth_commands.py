"""`login`, `logout`, `whoami`, `env` and `config` at the command level."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localstack_cli.auth.session import Credential, Session, load, save, session_path
from localstack_cli.auth.vault_token_file import VAULT_TOKEN, token_path
from localstack_cli.main import app
from tests.fixtures.cluster import FakeCluster

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

TOKENS = ("hvs.vault", "nomad-tok", "consul-tok")


def plain(text: str) -> str:
    return _ANSI.sub("", text)


@pytest.fixture
def logged_in(cluster_addr: str) -> Session:
    now = datetime.now(UTC)
    session = Session(
        method="userpass",
        vault_addr=cluster_addr,
        username="operator",
        vault=Credential(
            "hvs.vault",
            "vault-acc",
            now + timedelta(days=30),
            True,
            entity_id="351f302a",
            policies=("default",),
        ),
        nomad=Credential("nomad-tok", "nomad-acc", now + timedelta(minutes=25), True),
        consul=Credential("consul-tok", "consul-acc", now + timedelta(minutes=25), True),
    )
    save(session, session_path())
    return session


# --- env -------------------------------------------------------------------


def test_env_emits_both_consul_variable_names(logged_in: Session) -> None:
    """The single highest-value regression test here.

    The `consul` binary reads only `CONSUL_HTTP_TOKEN`, but this repo's
    terraform recipes bridge `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` by hand, so
    a stale `CONSUL_TOKEN` silently beats a fresh one inside every recipe.
    """
    result = runner.invoke(app, ["env"])
    assert result.exit_code == 0
    exports = dict(
        line.removeprefix("export ").split("=", 1) for line in result.stdout.strip().splitlines()
    )
    assert exports == {
        "VAULT_TOKEN": "hvs.vault",
        "NOMAD_TOKEN": "nomad-tok",
        "CONSUL_HTTP_TOKEN": "consul-tok",
        "CONSUL_TOKEN": "consul-tok",
    }


def test_env_stdout_is_only_export_lines(logged_in: Session) -> None:
    """A single log line on stdout makes `eval` execute garbage."""
    result = runner.invoke(app, ["env"])
    assert all(line.startswith("export ") for line in result.stdout.strip().splitlines())


def test_env_diagnostics_go_to_stderr_when_refreshing(
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
    result = runner.invoke(app, ["env"])
    assert result.exit_code == 0
    assert all(line.startswith("export ") for line in result.stdout.strip().splitlines())


def test_env_json_format(logged_in: Session) -> None:
    result = runner.invoke(app, ["env", "--format", "json"])
    assert json.loads(result.stdout)["CONSUL_TOKEN"] == "consul-tok"


def test_env_without_a_session_fails() -> None:
    result = runner.invoke(app, ["env"])
    assert result.exit_code != 0
    assert result.stdout == ""


# --- whoami ----------------------------------------------------------------


def test_whoami_prints_no_token_value(logged_in: Session) -> None:
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 0
    for token in TOKENS:
        assert token not in result.stdout
        assert token not in result.stderr


def test_whoami_reports_the_accessors_and_entity(logged_in: Session) -> None:
    """Accessors are the input to revoking a stolen session and cannot
    authenticate anything, so printing them is safe and useful."""
    result = runner.invoke(app, ["whoami"])
    assert "vault-acc" in result.stdout
    assert "nomad-acc" in result.stdout
    assert "351f302a" in result.stdout


def test_whoami_json_carries_no_token(logged_in: Session) -> None:
    result = runner.invoke(app, ["whoami", "--format", "json"])
    body = json.loads(result.stdout)
    assert body["entity_id"] == "351f302a"
    assert TOKENS[0] not in result.stdout


def test_whoami_says_which_token_a_bare_vault_would_use(
    logged_in: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(VAULT_TOKEN, "the-root-token")
    result = runner.invoke(app, ["whoami", "--format", "json"])
    assert json.loads(result.stdout)["bare_vault_uses_session"] is False


def test_whoami_without_a_session_exits_non_zero() -> None:
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code != 0


# --- the shadowing warning -------------------------------------------------


def test_the_warning_fires_when_the_environment_differs(
    logged_in: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails in the one direction nobody notices: the developer believes they
    are `operator` and they are root."""
    monkeypatch.setenv(VAULT_TOKEN, "the-root-token")
    result = runner.invoke(app, ["whoami"])
    assert "VAULT_TOKEN is set in this shell" in plain(result.stderr)
    assert 'eval "$(localstack env)"' in plain(result.stderr)


def test_the_warning_stays_off_stdout(logged_in: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VAULT_TOKEN, "the-root-token")
    result = runner.invoke(app, ["whoami"])
    assert "WARNING" not in result.stdout


def test_the_warning_is_quiet_when_the_environment_matches(
    logged_in: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The state after `eval "$(localstack env)"`. One that fires on every
    healthy session trains the operator to ignore it."""
    monkeypatch.setenv(VAULT_TOKEN, "hvs.vault")
    result = runner.invoke(app, ["whoami"])
    assert "VAULT_TOKEN is set in this shell" not in plain(result.stderr)


def test_the_warning_is_quiet_when_the_environment_is_unset(logged_in: Session) -> None:
    result = runner.invoke(app, ["whoami"])
    assert "VAULT_TOKEN is set in this shell" not in plain(result.stderr)


# --- logout ----------------------------------------------------------------


def test_logout_revokes_before_deleting(logged_in: Session, cluster: FakeCluster) -> None:
    """Deleting alone leaves live tokens on the cluster for up to an hour."""
    token_path().write_text("hvs.vault")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert cluster.requests_for("/v1/auth/token/revoke-self")[0].token == "hvs.vault"
    assert load(session_path()) is None
    assert not token_path().exists()


def test_logout_deletes_even_when_revocation_fails(
    logged_in: Session, cluster: FakeCluster
) -> None:
    """A stale token on disk is worse than none: the next `vault` command
    fails with a confusing 403 instead of an honest "not logged in"."""
    cluster.routes["/v1/auth/token/revoke-self"] = (403, b'{"errors":["denied"]}')
    token_path().write_text("hvs.vault")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code != 0
    assert load(session_path()) is None
    assert not token_path().exists()


def test_logout_prints_the_accessors_when_revocation_fails(
    logged_in: Session, cluster: FakeCluster
) -> None:
    cluster.routes["/v1/auth/token/revoke-self"] = (403, b'{"errors":["denied"]}')
    result = runner.invoke(app, ["logout"])
    stderr = plain(result.stderr)
    assert "vault-acc" in stderr and "nomad-acc" in stderr and "consul-acc" in stderr


def test_logout_without_a_session_exits_non_zero() -> None:
    result = runner.invoke(app, ["logout"])
    assert result.exit_code != 0


# --- login -----------------------------------------------------------------


def test_login_refuses_plaintext_before_prompting() -> None:
    """Before the prompt, so a refused address never collects a password."""
    result = runner.invoke(
        app, ["login", "--vault-addr", "http://192.168.2.30:8200"], input="hunter2\n"
    )
    assert result.exit_code != 0
    assert "vault.lab.orangecluster.nl" in plain(result.stderr)
    assert "Password" not in result.stdout


def test_login_rejects_an_unsupported_method() -> None:
    result = runner.invoke(app, ["login", "--method", "oidc"])
    assert result.exit_code != 0
    assert "unsupported method" in plain(result.stderr)


def test_login_writes_the_session_and_the_token_file(cluster_addr: str) -> None:
    result = runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert result.exit_code == 0
    session = load(session_path())
    assert session is not None
    assert session.username == "operator"
    assert session.vault.entity_id == "351f302a"
    assert session.nomad is not None and session.nomad.token == "nomad-secret-id"
    assert session.consul is not None and session.consul.token == "consul-token"
    assert token_path().read_text() == "hvs.session-token"


def test_login_brokers_eagerly(cluster_addr: str, cluster: FakeCluster) -> None:
    """So a missing grant fails here, naming the path, instead of inside a
    later `terraform apply`."""
    runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert len(cluster.requests_for("/v1/nomad/creds/deploy")) == 1
    assert len(cluster.requests_for("/v1/consul/creds/deploy")) == 1


def test_login_reports_a_denied_broker_without_hiding_that_it_authenticated(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """The fix is a policy grant, not a password, so the message must not
    read as a failed login."""
    cluster.routes["/v1/nomad/creds/deploy"] = (403, b'{"errors":["denied"]}')
    result = runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert result.exit_code != 0
    stderr = plain(result.stderr)
    assert "logged in as operator" in stderr
    assert "nomad/creds/deploy" in stderr
    assert "F11" in stderr


def test_login_never_writes_the_password_anywhere(cluster_addr: str) -> None:
    runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert "hunter2" not in session_path().read_text()


def test_login_puts_no_token_on_stdout(cluster_addr: str) -> None:
    result = runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert "hvs.session-token" not in result.stdout


def test_login_honours_the_username_environment_variable(
    cluster_addr: str, cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALSTACK_VAULT_USERNAME", "someone")
    cluster.routes["/v1/auth/userpass/login/someone"] = cluster.routes[
        "/v1/auth/userpass/login/operator"
    ]
    runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert cluster.requests_for("/v1/auth/userpass/login/someone")


# --- config ----------------------------------------------------------------


def test_config_prints_no_secret_material(
    logged_in: Session, monkeypatch: pytest.MonkeyPatch, cluster_addr: str
) -> None:
    """`config` is what a developer pastes into an issue, which is exactly
    why it must be safe to paste."""
    monkeypatch.setenv("VAULT_ADDR", cluster_addr)
    for form in ([], ["--format", "json"]):
        result = runner.invoke(app, ["config", *form])
        assert result.exit_code == 0
        for token in TOKENS:
            assert token not in result.stdout
        assert "hvs." not in result.stdout
        assert "vault-acc" not in result.stdout


def test_config_reports_the_addresses_and_the_session_shape(
    logged_in: Session, monkeypatch: pytest.MonkeyPatch, cluster_addr: str
) -> None:
    monkeypatch.setenv("VAULT_ADDR", cluster_addr)
    body = json.loads(runner.invoke(app, ["config", "--format", "json"]).stdout)
    assert body["vault_addr"] == cluster_addr
    assert body["edge_domain"] == "lab.orangecluster.nl"
    assert set(body["session"]["expires_at"]) == {"vault", "nomad", "consul"}


def test_config_works_without_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["config", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["session"] is None


def test_config_reports_a_missing_address_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VAULT_ADDR")
    result = runner.invoke(app, ["config"])
    assert result.exit_code != 0
    assert "VAULT_ADDR" in plain(result.stderr)


def test_the_session_file_is_not_in_the_repo(logged_in: Session) -> None:
    assert ".loop" not in str(session_path())
    assert Path.cwd() not in session_path().parents


# --- orphan prevention -----------------------------------------------------


def test_login_revokes_the_session_it_replaces(
    logged_in: Session, cluster: FakeCluster, cluster_addr: str
) -> None:
    """Overwriting the file without revoking leaves the old token live for
    weeks with nothing holding a reference. Ten such orphans were found on the
    live cluster while implementing this ticket."""
    runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    revokes = cluster.requests_for("/v1/auth/token/revoke-self")
    assert [item.token for item in revokes] == ["hvs.vault"]


def test_login_with_no_previous_session_revokes_nothing(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert cluster.requests_for("/v1/auth/token/revoke-self") == []


def test_login_revokes_its_own_token_when_brokering_fails(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """Nothing persists this token, so leaving it live would orphan one per
    retry against a missing grant."""
    cluster.routes["/v1/nomad/creds/deploy"] = (403, b'{"errors":["denied"]}')
    result = runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    assert result.exit_code != 0
    revokes = cluster.requests_for("/v1/auth/token/revoke-self")
    assert [item.token for item in revokes] == ["hvs.session-token"]


def test_logout_reports_but_does_not_delete_an_unattributable_token_file() -> None:
    """Deleting it would drop the only local reference to a credential that
    stays live on the cluster, which is the orphan this command prevents. And
    the file may belong to a plain `vault login`, not to this CLI."""
    token_path().write_text("hvs.orphan")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code != 0
    assert token_path().exists(), "must not delete a token it cannot revoke"
    assert "vault token revoke -self" in plain(result.stderr)


def test_logout_with_nothing_at_all_exits_non_zero() -> None:
    result = runner.invoke(app, ["logout"])
    assert result.exit_code != 0


def test_whoami_reports_the_group_granted_policy(cluster_addr: str) -> None:
    """End to end: log in against the measured response shape, then check the
    command a developer runs to see their own grants."""
    runner.invoke(app, ["login", "--vault-addr", cluster_addr], input="hunter2\n")
    result = runner.invoke(app, ["whoami"])
    assert "developer" in result.stdout


def test_logout_revokes_BEFORE_it_deletes(
    logged_in: Session, cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering, not just outcome.

    Asserting the accessor is dead and the file is gone passes for either
    order. Deleting first and then failing to revoke leaves live tokens on the
    cluster with nothing left pointing at them, so the order is the property.
    """
    seen_at_delete: list[int] = []

    def recording_delete(path: Path) -> bool:
        seen_at_delete.append(len(cluster.requests_for("/v1/auth/token/revoke-self")))
        return True

    monkeypatch.setattr("localstack_cli.commands.logout.delete", recording_delete)
    result = runner.invoke(app, ["logout"])

    assert result.exit_code == 0
    assert seen_at_delete == [1], "the revoke must already have happened when the file is deleted"


def test_a_failed_login_leaves_the_existing_session_untouched(
    logged_in: Session, cluster: FakeCluster
) -> None:
    """A mistyped password must not cost you a working session.

    An earlier revision revoked the previous session before attempting the
    login, so a typo destroyed it and left the cache holding a dead token.
    The next command then reported a missing F11 grant on a cluster where the
    grant was fine, which is the misdiagnosis R8 exists to prevent.
    """
    cluster.routes["/v1/auth/userpass/login/operator"] = (
        403,
        b'{"errors":["invalid username or password"]}',
    )
    result = runner.invoke(app, ["login", "--vault-addr", logged_in.vault_addr], input="wrong\n")
    assert result.exit_code != 0
    assert cluster.requests_for("/v1/auth/token/revoke-self") == [], (
        "a failed login must not revoke the session it did not replace"
    )
    still_there = load(session_path())
    assert still_there is not None
    assert still_there.vault.token == "hvs.vault"


def test_the_new_session_is_persisted_before_the_old_one_is_revoked(
    logged_in: Session, cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closes a crash window.

    Revoking first leaves a gap where a crash kills the old token, never
    writes the new one, and leaves the developer logged out holding an
    untracked live credential. Writing first means a crash in the remaining
    gap orphans only the OLD token, which is the pre-existing state, and the
    developer still has a working session.
    """
    revokes_at_save: list[int] = []
    real_save = save

    def recording_save(session: Session, path: Path) -> None:
        revokes_at_save.append(len(cluster.requests_for("/v1/auth/token/revoke-self")))
        real_save(session, path)

    monkeypatch.setattr("localstack_cli.commands.login.save", recording_save)
    result = runner.invoke(app, ["login", "--vault-addr", logged_in.vault_addr], input="hunter2\n")
    assert result.exit_code == 0
    assert revokes_at_save == [0], "the new session must be on disk before the old token is revoked"
    assert len(cluster.requests_for("/v1/auth/token/revoke-self")) == 1
