"""A real group for the lazy-loading tests to import.

Importing this module records the fact in `IMPORTED`, which is how a test can
tell whether the group was loaded eagerly or on dispatch. A stub in the test
file would not work: `LazyTyperGroup` calls `importlib.import_module`, so the
group has to be a module on disk.
"""

import typer

IMPORTED: list[str] = []
IMPORTED.append(__name__)

app = typer.Typer(no_args_is_help=True, help="A group that exists only for tests.")


@app.callback()
def group() -> None:
    """Keep this a group.

    A Typer app holding exactly one command and no callback collapses into
    that command, so `localstack demo` would run `ping` instead of listing
    it. Real groups need the same callback until they have two commands.
    """


@app.command()
def ping() -> None:
    """Print something a test can assert on."""
    typer.echo("pong")
