from importlib.metadata import version

from typer.testing import CliRunner

from localstack_cli.main import app

runner = CliRunner()


def test_version_matches_installed_metadata() -> None:
    """Assert against the metadata, not a literal.

    A hardcoded expectation here would pass while `--version` printed
    something that had drifted from pyproject.toml.
    """
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == version("localstack-cli")


def test_help_lists_the_version_flag() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--version" in result.output
