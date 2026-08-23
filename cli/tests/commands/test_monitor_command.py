"""`localstack monitor` as a command, not as a TUI.

The panel itself is covered by the snapshot tests. What matters here is that
the command is registered, takes its addresses from config, refuses to run
without a session, and never grows a second way to get a token.
"""

from typing import Any

import pytest
from typer.testing import CliRunner

from localstack_cli.main import app

runner = CliRunner()


def test_the_command_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert "monitor" in result.output


def test_the_help_names_the_refresh_flag() -> None:
    result = runner.invoke(app, ["monitor", "--help"])

    assert result.exit_code == 0
    assert "--refresh" in result.output


def test_a_missing_address_fails_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Addresses come from config.py, which names what is missing."""
    monkeypatch.delenv("NOMAD_ADDR", raising=False)

    result = runner.invoke(app, ["monitor"])

    assert result.exit_code == 1
    assert "NOMAD_ADDR" in result.output


def test_it_refuses_to_run_without_a_session() -> None:
    """Auth comes entirely from `login`. There is no fallback path."""
    result = runner.invoke(app, ["monitor"])

    assert result.exit_code == 1
    assert "localstack login" in result.output


def test_the_app_is_built_from_the_resolved_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command wires config into the panel and does not invent defaults."""
    from localstack_cli.tui import monitor as tui

    seen: dict[str, Any] = {}

    def capture(**kwargs: Any) -> Any:
        seen.update(kwargs)

        class NeverRuns:
            def run(self) -> None:
                return None

        return NeverRuns()

    monkeypatch.setattr("localstack_cli.tui.monitor.build", capture)
    monkeypatch.setattr("localstack_cli.commands.monitor.require_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "localstack_cli.commands.monitor.refreshed_session", lambda session: session
    )
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example.invalid")
    monkeypatch.setenv("NOMAD_ADDR", "https://nomad.example.invalid")
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "https://consul.example.invalid")

    result = runner.invoke(app, ["monitor", "--refresh", "0"])

    assert result.exit_code == 0, result.output
    assert seen["vault_addr"] == "https://vault.example.invalid"
    assert seen["nomad_addr"] == "https://nomad.example.invalid"
    assert seen["consul_addr"] == "https://consul.example.invalid"
    assert seen["nomad_token"] == "a-nomad-token"
    assert seen["refresh_seconds"] == 0
    assert tui.REFRESH_SECONDS == 5.0


class _FakeCredential:
    token = "a-nomad-token"


class _FakeSession:
    def credential(self, service: str) -> Any:
        return _FakeCredential() if service == "nomad_manage" else None
