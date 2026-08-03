"""`localstack breakglass`: section coverage, credential boundary, no-open.

The credential canary is the guardrail test: inject token-shaped values
into every credential env var, run every code path, and assert none of them
appears in stdout, stderr, or any file written. This is the row that turns
the operator's boundary into something a test can fail.
"""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localstack_cli.main import app

runner = CliRunner()

RUNBOOK = pytest.importorskip("localstack_cli.commands.breakglass")._load_runbook()


@pytest.fixture(autouse=True)
def probes_stay_local(monkeypatch: pytest.MonkeyPatch, closed_addr: str) -> None:
    """Point the probes at a closed local port, as the probe suite does.

    Without this, the probe-on tests resolve and dial the real cluster. The
    probes swallow every exception by design, so the suite stays green while
    the run has already left the machine.
    """
    breakglass = pytest.importorskip("localstack_cli.commands.breakglass")
    monkeypatch.setattr(breakglass, "EDGE", dict.fromkeys(breakglass.EDGE, closed_addr))
    monkeypatch.setattr(breakglass, "LAN", dict.fromkeys(breakglass.LAN, closed_addr))


# Every failure-mode section from requirement 2, by heading.
SECTIONS = [
    "Check your own connectivity first",
    "Vault is sealed",
    "Your token is expired or revoked",
    "Edge down, cluster up",
    "Nomad is unreachable",
    "Consul is unreachable",
    "Lost local token cache",
]


@pytest.mark.parametrize("heading", SECTIONS)
def test_every_section_appears_in_the_output(heading: str) -> None:
    result = runner.invoke(app, ["breakglass", "--no-probe"])
    assert result.exit_code == 0
    assert heading in result.stdout, f"missing section: {heading!r}"


@pytest.mark.parametrize("heading", SECTIONS)
def test_every_section_appears_in_the_runbook_text(heading: str) -> None:
    assert heading in RUNBOOK, f"section absent from the runbook source: {heading!r}"


# -- Credential boundary -----------------------------------------------------


CANARY_ENV = {
    "VAULT_TOKEN": "hvs.CANARYTOKEN",
    "VAULT_UNSEAL_KEY_1": "CANARYKEY1",
    "VAULT_UNSEAL_KEY_2": "CANARYKEY2",
    "VAULT_UNSEAL_KEY_3": "CANARYKEY3",
    "NOMAD_TOKEN": "CANARYNOMAD",
    "CONSUL_HTTP_TOKEN": "CANARYCONSUL",
    "CONSUL_TOKEN": "CANARYCONSUL2",
}

CANARY_VALUES = sorted(set(CANARY_ENV.values()), key=len, reverse=True)


@pytest.fixture
def canary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in CANARY_ENV.items():
        monkeypatch.setenv(name, value)


def test_no_canary_leaks_with_probes_off(canary_env: None, tmp_path: Path) -> None:
    result = runner.invoke(app, ["breakglass", "--no-probe"])
    assert result.exit_code == 0
    for value in CANARY_VALUES:
        assert value not in result.stdout, f"canary leaked to stdout: {value!r}"
        assert value not in result.stderr, f"canary leaked to stderr: {value!r}"


def test_no_canary_leaks_with_probes_on(canary_env: None) -> None:
    # Probes will fail (no cluster reachable), but the command must still
    # exit 0 and print the runbook without leaking a canary.
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    for value in CANARY_VALUES:
        assert value not in result.stdout, f"canary leaked to stdout: {value!r}"
        assert value not in result.stderr, f"canary leaked to stderr: {value!r}"


def test_no_token_shaped_string_in_the_runbook_text() -> None:
    # The runbook must not contain a real-looking token by accident.
    patterns = [r"hvs\.", r"hvb\.", r"s\.[A-Za-z0-9]{24}"]
    for pattern in patterns:
        assert re.search(pattern, RUNBOOK) is None, f"token-shaped string in runbook: {pattern!r}"


# -- The command never opens the init file -----------------------------------


def test_the_init_file_path_appears_as_text_but_is_never_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/opt/vault/init.json` must appear in the output as literal text but
    no filesystem read of it may be attempted."""

    opens: list[str] = []
    real_open = open

    def tracking_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        path_str = str(path)
        opens.append(path_str)
        if "init.json" in path_str:
            pytest.fail(f"breakglass opened the init file: {path_str}")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", tracking_open)
    result = runner.invoke(app, ["breakglass", "--no-probe"])
    assert result.exit_code == 0
    assert "/opt/vault/init.json" in result.stdout
    init_reads = [p for p in opens if "init.json" in p]
    assert init_reads == [], f"breakglass read the init file: {init_reads}"


# -- Exit code ---------------------------------------------------------------


def test_exit_code_is_always_zero_with_probes_off() -> None:
    result = runner.invoke(app, ["breakglass", "--no-probe"])
    assert result.exit_code == 0


def test_exit_code_is_zero_even_when_probes_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Point probes at a closed port so every probe fails. The command must
    # still exit 0 and print the runbook.
    from localstack_cli.commands import breakglass as bg

    monkeypatch.setattr(
        bg,
        "EDGE",
        {
            "vault": "http://127.0.0.1:1",
            "nomad": "http://127.0.0.1:1",
            "consul": "http://127.0.0.1:1",
        },
    )
    monkeypatch.setattr(
        bg,
        "LAN",
        {
            "vault": "http://127.0.0.1:1",
            "nomad": "http://127.0.0.1:1",
            "consul": "http://127.0.0.1:1",
        },
    )
    result = runner.invoke(app, ["breakglass"])
    assert result.exit_code == 0
    # The runbook must still print when every probe fails.
    assert "Check your own connectivity first" in result.stdout


# -- Single source -----------------------------------------------------------


def test_runbook_prints_from_outside_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runbook lives inside the package, loaded with importlib.resources,
    so it prints regardless of the working directory."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["breakglass", "--no-probe"])
    assert result.exit_code == 0
    assert "Vault is sealed" in result.stdout
