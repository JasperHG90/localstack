"""`~/.vault-token`: the write, the removal, and what outranks it.

The autouse fixture points `HOME` at a temp directory, so these touch a real
file and never the developer's own.
"""

import os
import stat
from pathlib import Path

import pytest

from localstack_cli.auth import vault_token_file
from localstack_cli.auth.vault_token_file import (
    VAULT_TOKEN,
    current_token,
    env_token_differs,
)


def test_the_environment_token_wins_over_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Matches the Vault CLI's own order, so the CLI reports what a command
    would really send rather than what it wishes were true."""
    (Path.home() / ".vault-token").write_text("from-file\n")
    monkeypatch.setenv(VAULT_TOKEN, "from-env")
    assert current_token() == "from-env"


def test_the_token_file_is_used_when_the_environment_is_empty() -> None:
    (Path.home() / ".vault-token").write_text("from-file\n")
    assert current_token() == "from-file"


def test_no_token_anywhere_is_none() -> None:
    assert current_token() is None


def test_an_empty_token_file_is_none() -> None:
    """An empty file is not a token, and truthiness would call it one."""
    (Path.home() / ".vault-token").write_text("   \n")
    assert current_token() is None


def test_write_creates_the_file_at_0600() -> None:
    path = vault_token_file.write("hvs.atoken")
    assert path.read_text() == "hvs.atoken"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_write_leaves_no_temp_file_behind() -> None:
    home = Path.home()
    before = set(home.iterdir())
    vault_token_file.write("hvs.atoken")
    leftovers = [p for p in home.iterdir() if p not in before and p.name != ".vault-token"]
    assert leftovers == [], "the temp file should be renamed away, not left behind"


def test_write_sets_the_mode_at_creation_not_afterwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chmod after writing leaves a window in which the token is world
    readable, and the FINAL mode is 0600 either way -- so asserting on the
    final mode cannot tell the two apart. Observe the creation instead.
    """
    modes: list[int] = []
    real_open = os.open

    def recording_open(path: object, flags: int, mode: int = 0o777) -> int:
        modes.append(mode)
        return real_open(path, flags, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", recording_open)
    vault_token_file.write("hvs.atoken")
    assert modes == [0o600], f"token file created with {[oct(m) for m in modes]}"


def test_write_replaces_an_existing_file() -> None:
    vault_token_file.write("first")
    vault_token_file.write("second")
    assert (Path.home() / ".vault-token").read_text() == "second"


def test_remove_deletes_the_file_and_reports_it() -> None:
    vault_token_file.write("hvs.atoken")
    assert vault_token_file.remove() is True
    assert not (Path.home() / ".vault-token").exists()


def test_remove_is_quiet_when_there_is_no_file() -> None:
    assert vault_token_file.remove() is False


def test_env_token_differs_reports_the_shadowing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(VAULT_TOKEN, "the-root-token")
    assert env_token_differs("the-session-token") == "the-root-token"


def test_env_token_differs_is_quiet_when_they_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """The state after `eval "$(localstack env)"`.

    A warning that fires on every healthy session trains the operator to
    ignore it, which costs exactly the case it exists to catch.
    """
    monkeypatch.setenv(VAULT_TOKEN, "the-session-token")
    assert env_token_differs("the-session-token") is None


def test_env_token_differs_is_quiet_when_unset() -> None:
    assert env_token_differs("the-session-token") is None


def test_the_token_path_is_under_home() -> None:
    """Guards the fixture as much as the code: a test that wrote the real
    `~/.vault-token` would log the developer out."""
    assert vault_token_file.token_path() == Path(os.environ["HOME"]) / ".vault-token"


def test_a_leftover_temp_file_does_not_block_a_later_write() -> None:
    """Same collision as the session cache: a temp file from a killed run
    must not lock the developer out of writing a new token."""
    (Path.home() / f".vault-token.{os.getpid()}").write_text("stale")
    vault_token_file.write("hvs.fresh")
    assert (Path.home() / ".vault-token").read_text() == "hvs.fresh"
