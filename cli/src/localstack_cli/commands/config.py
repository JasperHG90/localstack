"""`localstack config`: what to paste into an issue, with nothing secret in it.

Addresses come from D1's `Config.from_env()`; this command adds only the
session's non-secret fields. It is safe to paste, which is the requirement,
so no token, no password, no accessor and no session field beyond these.
"""

import json
import sys

import typer

from localstack_cli.auth.session import SessionError, load, session_path
from localstack_cli.commands._common import fail
from localstack_cli.config import Config, ConfigError

app = typer.Typer()

EDGE_DOMAIN = "lab.orangecluster.nl"


@app.command()
def config(
    output: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Print the resolved addresses and the session's non-secret fields."""
    if output not in ("text", "json"):
        raise fail(f"unknown format {output!r}. Expected `text` or `json`.")

    try:
        addresses = Config.from_env()
    except ConfigError as error:
        raise fail(str(error)) from error

    report: dict[str, object] = {
        "vault_addr": addresses.vault_addr,
        "nomad_addr": addresses.nomad_addr,
        "consul_addr": addresses.consul_addr,
        "edge_domain": EDGE_DOMAIN,
        "session_file": str(session_path()),
    }

    try:
        session = load(session_path())
    except SessionError as error:
        report["session"] = f"unreadable: {error}"
        session = None
    if session is not None:
        report["session"] = {
            "version": session.version,
            "method": session.method,
            "username": session.username,
            "vault_addr": session.vault_addr,
            "expires_at": {
                name: entry.expires_at.isoformat()
                for name in ("vault", "nomad", "consul")
                if (entry := session.credential(name)) is not None
            },
        }
    elif "session" not in report:
        report["session"] = None

    if output == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
        return

    sys.stdout.write(f"vault   {addresses.vault_addr}\n")
    sys.stdout.write(f"nomad   {addresses.nomad_addr}\n")
    sys.stdout.write(f"consul  {addresses.consul_addr}\n")
    sys.stdout.write(f"edge    *.{EDGE_DOMAIN}\n")
    sys.stdout.write(f"session {session_path()}\n")
    if session is None:
        sys.stdout.write("        (no session)\n")
        return
    sys.stdout.write(f"        {session.username} via {session.method}\n")
    for name in ("vault", "nomad", "consul"):
        entry = session.credential(name)
        if entry is not None:
            sys.stdout.write(f"        {name} expires {entry.expires_at.isoformat()}\n")
