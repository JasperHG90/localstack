"""`localstack env`: shell exports for `eval "$(localstack env)"`.

Emits BOTH Consul spellings. The `consul` binary reads `CONSUL_HTTP_TOKEN`
and never `CONSUL_TOKEN`, but this repo's terraform recipes bridge
`CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` by hand, so a stale `CONSUL_TOKEN` left
in the shell silently overwrites a fresh one inside every `just` recipe.
Emitting only the name the binary reads is not enough.

Emitting `VAULT_TOKEN` is what makes the eval the one move that actually
demotes this shell from the injected root token to the session.
"""

import json
import sys

import typer

from localstack_cli.commands._common import fail, refreshed_session, require_session

app = typer.Typer()


@app.command()
def env(
    output: str = typer.Option("shell", "--format", help="shell or json"),
) -> None:
    """Print the session's tokens as shell exports. Diagnostics go to stderr."""
    if output not in ("shell", "json"):
        raise fail(f"unknown format {output!r}. Expected `shell` or `json`.")

    session = refreshed_session(require_session())
    if session.nomad is None or session.consul is None:
        raise fail("the session has no brokered tokens. Run `localstack login`.")

    values = {
        "VAULT_TOKEN": session.vault.token,
        "NOMAD_TOKEN": session.nomad.token,
        "CONSUL_HTTP_TOKEN": session.consul.token,
        "CONSUL_TOKEN": session.consul.token,
    }

    if output == "json":
        sys.stdout.write(json.dumps(values, indent=2) + "\n")
        return
    for name, value in values.items():
        sys.stdout.write(f"export {name}={value}\n")
