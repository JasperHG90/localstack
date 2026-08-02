"""`localstack whoami`: who the session is, and which token a bare `vault` uses.

Never prints a token value. It prints accessors, which are the input to
revoking a stolen session and are useless for authenticating.
"""

import json
import sys

import typer

from localstack_cli.auth import vault_token_file
from localstack_cli.auth.session import Credential, Session
from localstack_cli.commands._common import fail, require_session, warn_if_environment_shadows

app = typer.Typer()


def _describe(entry: Credential | None) -> dict[str, object] | None:
    if entry is None:
        return None
    return {
        "accessor": entry.accessor,
        "lease_id": entry.lease_id,
        "expires_at": entry.expires_at.isoformat(),
        "seconds_left": entry.seconds_left(),
    }


def _report(session: Session) -> dict[str, object]:
    return {
        "username": session.username,
        "method": session.method,
        "vault_addr": session.vault_addr,
        "entity_id": session.vault.entity_id,
        "policies": list(session.vault.policies),
        "vault": _describe(session.vault),
        "nomad": _describe(session.nomad),
        "consul": _describe(session.consul),
        "bare_vault_uses_session": vault_token_file.current_token() == session.vault.token,
    }


@app.command()
def whoami(
    output: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Report the session. Exits non-zero when there is none."""
    if output not in ("text", "json"):
        raise fail(f"unknown format {output!r}. Expected `text` or `json`.")

    session = require_session()
    report = _report(session)

    if output == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    else:
        sys.stdout.write(f"user      {session.username} ({session.method})\n")
        sys.stdout.write(f"vault     {session.vault_addr}\n")
        sys.stdout.write(f"entity    {session.vault.entity_id or '(none)'}\n")
        sys.stdout.write(f"policies  {', '.join(session.vault.policies) or '(none)'}\n")
        for name in ("vault", "nomad", "consul"):
            entry = session.credential(name)
            if entry is None:
                sys.stdout.write(f"{name:9} not brokered\n")
                continue
            sys.stdout.write(
                f"{name:9} accessor {entry.accessor} ({entry.seconds_left() // 60}m left)\n"
            )
        # The question a developer actually has, answered without them
        # needing to know that a file and a variable both exist.
        answer = "this session" if report["bare_vault_uses_session"] else "NOT this session"
        sys.stdout.write(f"bare vault uses {answer}\n")

    warn_if_environment_shadows(session)
