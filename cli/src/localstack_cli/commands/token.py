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

`localstack token s3 ROLE` is the one service the shims never call. S3 needs
three values, so it prints them as `export` lines for
`eval "$(localstack token s3 ROLE)"`, and rule 2 holds for it too.
"""

import shlex
import sys

import typer

from localstack_cli.auth import sts
from localstack_cli.commands._common import fail, refreshed_session, require_session

app = typer.Typer()

SERVICES = ("vault", "nomad", "consul")


@app.command()
def token(
    service: str = typer.Argument(..., help="vault, nomad, consul or s3"),
    role: str = typer.Argument("", help="s3 only: the role to assume, e.g. local-ov-sync"),
    endpoint: str = typer.Option(
        sts.DEFAULT_ENDPOINT, "--endpoint", help="s3 only: SeaweedFS's STS endpoint."
    ),
) -> None:
    """Print the current token for a service, refreshing it if stale.

    `s3 ROLE` prints S3 credentials for that role as shell exports, valid 15
    minutes.
    """
    if service == "s3":
        _s3(role, endpoint)
        return
    if service not in SERVICES:
        raise fail(f"unknown service {service!r}. Expected one of: {', '.join(SERVICES)}, s3.")

    session = refreshed_session(require_session())
    entry = session.credential(service)
    if entry is None or not entry.token:
        raise fail(f"no {service} token in the session. Run `localstack login`.")

    # Not typer.echo: no styling layer, nothing that could learn to add a
    # newline policy or a colour code later.
    sys.stdout.write(entry.token + "\n")


def _s3(role: str, endpoint: str) -> None:
    if not role:
        raise fail("s3 needs a role: `localstack token s3 ROLE`.")
    session = refreshed_session(require_session())
    try:
        creds = sts.s3_credentials(
            session.vault_addr, session.vault.token, role, endpoint, f"local-{session.username}"
        )
    except sts.StsError as error:
        raise fail(str(error)) from error
    print(f"{role} credentials expire at {creds.expiration}", file=sys.stderr)
    for name, value in creds.exports().items():
        sys.stdout.write(f"export {name}={shlex.quote(value)}\n")
