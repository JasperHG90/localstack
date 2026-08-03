"""The live-cluster rows, against real Vault, Nomad and Consul.

Excluded from the default run by `addopts = "-m 'not cluster'"`. Run them on
purpose:

    uv run pytest -m cluster

They need `VAULT_ADDR` reachable and a token that can read
`secret/default/vault/operator`, which is how the password is obtained. Every
test cleans up after itself: the module-scoped session is revoked at the end,
so the run adds no accessors to the cluster.
"""

import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.cluster

EDGE_VAULT = "https://vault.lab.orangecluster.nl"

# Captured at import, which happens during collection and therefore BEFORE the
# suite-wide autouse fixture points every address at a closed port. Without
# this the live rows inherit that and cannot reach the real cluster.
REAL_ADDRESSES = {
    name: os.environ.get(name, "") for name in ("VAULT_ADDR", "NOMAD_ADDR", "CONSUL_HTTP_ADDR")
}


def vault_cli(*args: str) -> str:
    result = subprocess.run(["vault", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        pytest.skip(f"vault {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


@pytest.fixture(scope="module")
def password() -> str:
    return vault_cli("kv", "get", "-field=password", "secret/default/vault/operator")


@pytest.fixture
def cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway HOME so a live run never touches the developer's session."""
    # The suite-wide autouse fixture already created this, so exist_ok is not
    # optional. Without it every row here errors before it runs.
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    for name, value in REAL_ADDRESSES.items():
        if not value:
            pytest.skip(f"{name} is not set; these rows need the live cluster")
        monkeypatch.setenv(name, value)
    return home


def run_cli(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    # `--no-sync` is load-bearing. `HOME` is redirected to a temp directory
    # for these rows, so a syncing `uv run` finds an empty cache there and
    # rebuilds `.venv` underneath the pytest process that is running it. The
    # parent then loses the certifi bundle mid-suite and every later HTTPS
    # call dies with a bare FileNotFoundError from `ssl`.
    return subprocess.run(
        ["uv", "run", "--no-sync", "localstack", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=dict(os.environ),
        check=False,
    )


@pytest.fixture
def live_session(cli_home: Path, password: str) -> Iterator[Path]:
    result = run_cli("login", "--vault-addr", EDGE_VAULT, stdin=password + "\n")
    assert result.returncode == 0, result.stderr
    session = cli_home / ".config" / "localstack" / "session.json"
    assert session.exists()
    try:
        yield session
    finally:
        run_cli("logout")


def test_a_real_login_yields_an_entity_bearing_token(live_session: Path) -> None:
    """The property F2's userpass backend exists to provide. The bootstrap
    root token has an empty entity_id, so a check for "a token came back"
    would pass against a token nothing can gate on."""
    data = json.loads(live_session.read_text())
    assert data["vault"]["entity_id"], "login produced no entity"


def test_the_three_expiries_differ(live_session: Path) -> None:
    data = json.loads(live_session.read_text())
    expiries = {data[name]["expires_at"] for name in ("vault", "nomad", "consul")}
    assert len(expiries) == 3


def test_the_brokered_tokens_are_real(live_session: Path) -> None:
    """Against the actual services, not against the session file."""
    data = json.loads(live_session.read_text())
    nomad = subprocess.run(
        ["nomad", "acl", "token", "self"],
        env=dict(os.environ, NOMAD_TOKEN=data["nomad"]["token"]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert nomad.returncode == 0, nomad.stderr
    assert "client" in nomad.stdout

    consul = subprocess.run(
        ["consul", "acl", "token", "read", "-self"],
        env=dict(os.environ, CONSUL_HTTP_TOKEN=data["consul"]["token"]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert consul.returncode == 0, consul.stderr


def test_token_stdout_is_exactly_the_token(live_session: Path) -> None:
    data = json.loads(live_session.read_text())
    for service in ("vault", "nomad", "consul"):
        result = run_cli("token", service)
        assert result.returncode == 0
        assert result.stdout == data[service]["token"] + "\n"


def test_plaintext_is_refused_against_the_real_address(cli_home: Path) -> None:
    result = run_cli("login", "--vault-addr", "http://192.168.2.30:8200")
    assert result.returncode != 0
    assert result.stdout == ""
    assert "vault.lab.orangecluster.nl" in result.stderr


def test_logout_revokes_and_the_revoke_cascades(cli_home: Path, password: str) -> None:
    """Revoking the parent Vault token must kill the brokered Nomad token,
    without this CLI touching Nomad."""
    assert run_cli("login", "--vault-addr", EDGE_VAULT, stdin=password + "\n").returncode == 0
    session = cli_home / ".config" / "localstack" / "session.json"
    data = json.loads(session.read_text())
    vault_accessor = data["vault"]["accessor"]
    nomad_accessor = data["nomad"]["accessor"]

    assert run_cli("logout").returncode == 0
    assert not session.exists()

    dead = subprocess.run(
        ["vault", "write", "auth/token/lookup-accessor", f"accessor={vault_accessor}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dead.returncode != 0, "the Vault accessor should be revoked"

    nomad = subprocess.run(
        ["nomad", "acl", "token", "info", nomad_accessor],
        capture_output=True,
        text=True,
        check=False,
    )
    assert nomad.returncode != 0, "the brokered Nomad token should have cascaded"


def test_a_second_login_revokes_the_first(cli_home: Path, password: str) -> None:
    """The orphan defect: before this, logging in twice left the first token
    live for weeks with nothing referencing it."""
    assert run_cli("login", "--vault-addr", EDGE_VAULT, stdin=password + "\n").returncode == 0
    session = cli_home / ".config" / "localstack" / "session.json"
    first = json.loads(session.read_text())["vault"]["accessor"]

    assert run_cli("login", "--vault-addr", EDGE_VAULT, stdin=password + "\n").returncode == 0
    second = json.loads(session.read_text())["vault"]["accessor"]
    assert first != second

    dead = subprocess.run(
        ["vault", "write", "auth/token/lookup-accessor", f"accessor={first}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dead.returncode != 0, "the replaced session should have been revoked"
    run_cli("logout")
