"""The lazy group wiring.

`_lazy.py` is vendored verbatim from aim, so these test that it is wired into
our root app and behaves against our typer version, not that aim's code is
correct.
"""

import re
import sys
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from localstack_cli._lazy import LAZY_SUBCOMMANDS
from localstack_cli.main import app

runner = CliRunner()

DEMO = "tests.fixtures.lazy_demo"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(output: str) -> str:
    return _ANSI.sub("", output)


@pytest.fixture
def registered() -> Iterator[None]:
    """Register a lazy group and unload it, so each test starts cold."""
    LAZY_SUBCOMMANDS["demo"] = f"{DEMO}:app"
    sys.modules.pop(DEMO, None)
    try:
        yield
    finally:
        del LAZY_SUBCOMMANDS["demo"]
        sys.modules.pop(DEMO, None)


def test_the_root_app_uses_the_lazy_group() -> None:
    """Without this the registry is inert and every test below passes for the
    wrong reason."""
    from typer.main import get_command

    from localstack_cli._lazy import LazyTyperGroup

    assert isinstance(get_command(app), LazyTyperGroup)


def test_a_lazy_group_is_listed_in_help(registered: None) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "demo" in plain(result.stdout)


def test_a_lazy_group_dispatches(registered: None) -> None:
    result = runner.invoke(app, ["demo", "ping"])
    assert result.exit_code == 0
    assert "pong" in plain(result.stdout)


def test_the_group_is_not_imported_until_it_is_needed(registered: None) -> None:
    """The whole point: `localstack --version` must not pay for a group's
    dependencies."""
    assert DEMO not in sys.modules
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert DEMO not in sys.modules, "asking for the version imported a group"


def test_dispatching_imports_the_group(registered: None) -> None:
    """The other half of the claim above: deferred, not skipped."""
    assert DEMO not in sys.modules
    runner.invoke(app, ["demo", "ping"])
    assert DEMO in sys.modules


def test_a_typo_suggests_the_lazy_group(registered: None) -> None:
    """Typer matches suggestions against eagerly registered commands only, so
    this is the behaviour `resolve_command` is overridden to restore."""
    result = runner.invoke(app, ["demp"])
    assert result.exit_code != 0
    assert "demo" in plain(result.output + result.stderr)


def test_a_lazy_group_with_no_arguments_prints_its_help(registered: None) -> None:
    """Every group sets `no_args_is_help=True`; bare `localstack demo` should
    explain itself rather than error."""
    result = runner.invoke(app, ["demo"])
    assert "ping" in plain(result.stdout)
