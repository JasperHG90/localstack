"""`localstack vault grants <job>`: which secret paths a job can reach.

The `nomad-workloads` policy grants each workload access to its own secrets
by templating the path on the calling entity's alias metadata. Read raw, it
tells a developer nothing about their job. This substitutes the job id and
namespace and shows both columns, so what was substituted stays visible.

It is a rendering of policy text, not an authorization decision, and it says
so in a footer. Vault resolves these templates per request against the
calling entity; this resolves them from arguments.
"""

import typer

from localstack_cli.api import grants as api_grants
from localstack_cli.api import vault as api_vault
from localstack_cli.api.errors import ClusterError
from localstack_cli.commands._common import fail, refreshed_session, require_session, warn
from localstack_cli.commands._session import explain
from localstack_cli.commands.render import GRANTS_FOOTER, emit_json, table
from localstack_cli.config import Config, ConfigError

app = typer.Typer(no_args_is_help=True)

# Pinned. A `--policy` option would be the cut `vault policy <name>` mirror
# in another shape: this command exists to answer "what can MY job read",
# not to dump an arbitrary policy.
WORKLOAD_POLICY = "nomad-workloads"


@app.callback()
def vault() -> None:
    """Vault views the native CLI does not offer."""


@app.command()
def grants(
    job: str = typer.Argument(..., help="The Nomad job id to resolve the policy for."),
    namespace: str = typer.Option("default", "--namespace", help="The Nomad namespace."),
    as_json: bool = typer.Option(False, "--json", help="Emit the result as JSON."),
) -> None:
    """Show which Vault paths a Nomad job's workload identity can reach."""
    try:
        config = Config.from_env()
    except ConfigError as error:
        raise fail(str(error)) from error

    session = refreshed_session(require_session())
    entry = session.credential("vault")
    if entry is None or not entry.token:
        raise fail("no Vault token in the session. Run `localstack login`.")

    try:
        text = api_vault.read_policy(config.vault_addr, entry.token, WORKLOAD_POLICY)
    except ClusterError as error:
        raise explain(error, config.vault_addr, entry.token) from error

    resolved = api_grants.render(text, {"nomad_namespace": namespace, "nomad_job_id": job})
    if not resolved:
        raise fail(f"policy {WORKLOAD_POLICY!r} has no path blocks.")

    if as_json:
        emit_json(resolved)
        return

    unresolved = [grant for grant in resolved if grant.unresolved]
    table(
        f"{WORKLOAD_POLICY} resolved for job {job!r} in namespace {namespace!r}",
        ["resolved path", "capabilities", "raw"],
        [
            [
                grant.resolved_path,
                ", ".join(grant.capabilities),
                grant.raw_path,
            ]
            for grant in resolved
        ],
        footer=GRANTS_FOOTER,
    )
    if unresolved:
        # Left visible rather than blanked: a resolved-looking path that is
        # wrong is worse than an obviously incomplete one.
        warn(
            f"{len(unresolved)} path(s) carry a variable this command cannot fill. "
            "They are shown with the `{{...}}` left in."
        )
