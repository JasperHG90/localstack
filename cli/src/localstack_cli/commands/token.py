"""`localstack token <svc>`: the token, and nothing else, on stdout.

This is the backend the PATH shims call. The shim does

    T="$(localstack token nomad)"

and puts `$T` straight into `NOMAD_TOKEN`, so one stray byte on stdout
becomes an invalid token and a 403 that reads like a permissions bug. Two
rules follow, and they are why this command has its own module with no
shared output helper in reach:

1. Stdout is the token and a single newline. Every diagnostic goes to stderr.
2. Failure is a non-zero exit with EMPTY stdout. The shim's fall-through to
   the unmodified binary is only safe because a failure produces nothing to
   export.
"""

import sys

import typer

from localstack_cli.commands._common import fail, refreshed_session, require_session

app = typer.Typer()

SERVICES = ("vault", "nomad", "consul")


@app.command()
def token(service: str = typer.Argument(..., help="vault, nomad or consul")) -> None:
    """Print the current token for a service, refreshing it if stale."""
    if service not in SERVICES:
        raise fail(f"unknown service {service!r}. Expected one of: {', '.join(SERVICES)}.")

    session = refreshed_session(require_session())
    entry = session.credential(service)
    if entry is None or not entry.token:
        raise fail(f"no {service} token in the session. Run `localstack login`.")

    # Not typer.echo: no styling layer, nothing that could learn to add a
    # newline policy or a colour code later.
    sys.stdout.write(entry.token + "\n")
