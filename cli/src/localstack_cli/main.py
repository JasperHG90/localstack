"""The `localstack` entrypoint.

Deliberately bare. D2 adds `login` and the broker commands, D3 the read
commands, D4 the TUI and D5 breakglass. Empty typer groups are not scaffolded
here: an empty group is a guess about a later ticket's shape.
"""

from importlib.metadata import version

import typer

app = typer.Typer(
    name="localstack",
    help="Cockpit for the localstack home-lab cluster.",
)


def _version_callback(value: bool) -> None:
    if value:
        # Read from the installed distribution rather than a literal, so this
        # cannot drift from pyproject.toml.
        typer.echo(version("localstack-cli"))
        raise typer.Exit


@app.callback()
def root(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Cockpit for the localstack home-lab cluster."""


def main() -> None:
    app()
