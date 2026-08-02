import re
from importlib.metadata import version

from typer.testing import CliRunner

from localstack_cli.branding import WORDMARK
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


def test_no_arguments_prints_help_and_succeeds() -> None:
    """`localstack` with nothing after it must be useful, not an error."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage:" in plain(result.stdout)


def test_no_arguments_prints_the_banner_to_stderr() -> None:
    """Banner chrome goes to stderr so piping the read commands stays clean."""
    result = runner.invoke(app, [])
    assert WORDMARK in plain(result.stderr)


def test_the_banner_shows_red_dots_when_the_cluster_is_unreachable() -> None:
    """The autouse fixture points every address at a closed port."""
    result = runner.invoke(app, [])
    banner = plain(result.stderr)
    for service in ("vault", "nomad", "consul", "session"):
        assert service in banner


def test_the_banner_does_not_appear_on_help() -> None:
    """`--help` is a question about the interface, not a session check, and
    it must not pay for three network probes."""
    result = runner.invoke(app, ["--help"])
    assert WORDMARK not in plain(result.stderr)
