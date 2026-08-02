import re
from importlib.metadata import version

from typer.testing import CliRunner

from localstack_cli.main import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(output: str) -> str:
    """Strip ANSI styling from CLI output.

    Typer renders help through rich, which colorises when it detects a
    terminal and does not otherwise. Those escapes land *inside* option
    names, so a bare `"--version" in result.output` passes uncoloured and
    fails coloured. Assert against the text, not the styling.
    """
    return _ANSI.sub("", output)


def test_version_matches_installed_metadata() -> None:
    """Assert against the metadata, not a literal.

    A hardcoded expectation here would pass while `--version` printed
    something that had drifted from pyproject.toml.
    """
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert plain(result.output).strip() == version("localstack-cli")


def test_help_lists_the_version_flag() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--version" in plain(result.output)
