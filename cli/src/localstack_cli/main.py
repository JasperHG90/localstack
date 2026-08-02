"""The `localstack` entrypoint.

Deliberately bare. D2 adds `login` and the broker commands, D3 the read
commands, D4 the TUI and D5 breakglass. Empty typer groups are not scaffolded
here: an empty group is a guess about a later ticket's shape.

Every group added later must pass `no_args_is_help=True`, so a bare
`localstack <group>` prints its help instead of an error. The root does the
same thing through the callback below, which also gets it a banner.

Groups register lazily rather than importing at module scope, so bare
`localstack` and `localstack --version` pay for no group's dependencies::

    LAZY_SUBCOMMANDS["login"] = "localstack_cli.commands.login:app"

The module is imported when the command runs, or when `--help` asks each
group for its short help.

A group holding exactly one command and no callback collapses into that
command, so `localstack login` would run the single subcommand rather than
list it. Give each group a `@app.callback()` until it has two commands.
"""

from importlib.metadata import version

import typer

from localstack_cli._lazy import LAZY_SUBCOMMANDS, LazyTyperGroup
from localstack_cli.branding import print_banner
from localstack_cli.status import probe_cluster

app = typer.Typer(
    name="localstack",
    cls=LazyTyperGroup,
    help="Cockpit for the localstack home-lab cluster.",
)

# D2's auth surface. Each module holds a single-command Typer, so it
# materializes as a top-level command rather than a group, and none of them is
# imported until one is dispatched. That matters most for `token`, which the
# PATH shims call on every `nomad`, `consul` and `vault` invocation.
LAZY_SUBCOMMANDS.update(
    {
        "login": "localstack_cli.commands.login:app",
        "logout": "localstack_cli.commands.logout:app",
        "whoami": "localstack_cli.commands.whoami:app",
        "env": "localstack_cli.commands.env:app",
        "token": "localstack_cli.commands.token:app",
        "config": "localstack_cli.commands.config:app",
    }
)


def _version_callback(value: bool) -> None:
    if value:
        # Read from the installed distribution rather than a literal, so this
        # cannot drift from pyproject.toml.
        typer.echo(version("localstack-cli"))
        raise typer.Exit


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Cockpit for the localstack home-lab cluster."""
    if ctx.invoked_subcommand is not None:
        return
    # Bare `localstack`. Click's own `no_args_is_help` would print help before
    # this callback ever ran, so the banner is emitted here and help follows.
    print_banner(probe_cluster())
    typer.echo(ctx.get_help())


def main() -> None:
    app()
