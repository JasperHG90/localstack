"""`localstack status`: Vault, Nomad and Consul in one view.

The value is the joint answer. Three separate commands make you run three
things and hold the result in your head; this fetches all three at once and
shows which of them is unhappy.

A section that failed says so and the command exits non-zero. Three green
panels produced by a swallowed timeout is the failure this guards.
"""

import typer

from localstack_cli.api import status as api_status
from localstack_cli.api.consul import failing
from localstack_cli.api.health import Health, judge_all
from localstack_cli.commands._common import fail, refreshed_session, require_session
from localstack_cli.commands.render import CONSUL_FILTER_FOOTER, emit_json, table
from localstack_cli.config import Config, ConfigError

app = typer.Typer()


@app.command()
def status(
    as_json: bool = typer.Option(False, "--json", help="Emit the result as JSON."),
) -> None:
    """Vault seal state, nodes, job health and failing Consul checks."""
    try:
        config = Config.from_env()
    except ConfigError as error:
        raise fail(str(error)) from error

    session = refreshed_session(require_session())
    nomad_entry = session.credential("nomad_manage")

    result = api_status.fetch(
        vault_addr=config.vault_addr,
        nomad_addr=config.nomad_addr,
        consul_addr=config.consul_addr,
        nomad_token=nomad_entry.token if nomad_entry else None,
    )

    if as_json:
        emit_json(result)
    else:
        _render(result)

    if not result.ok:
        # Naming them again on the way out, because the table may have
        # scrolled by the time a script reads the exit code.
        raise typer.Exit(1)


def _render(result: api_status.ClusterStatus) -> None:
    rows = []

    if result.vault.ok and result.vault.value is not None:
        health = result.vault.value
        seal = "SEALED" if health.sealed else "unsealed"
        rows.append(["vault", seal, f"version {health.version}"])
    else:
        rows.append(["vault", "ERROR", result.vault.error or ""])

    if result.nodes.ok and result.nodes.value is not None:
        nodes = result.nodes.value
        usable = sum(1 for node in nodes if node.usable)
        rows.append(["nodes", f"{usable}/{len(nodes)} ready", ""])
    else:
        rows.append(["nodes", "ERROR", result.nodes.error or ""])

    if result.jobs.ok and result.jobs.value is not None:
        nodes = result.nodes.value or []
        verdicts = judge_all(result.jobs.value, nodes)
        unhealthy = [v for v in verdicts if v.health is not Health.HEALTHY]
        summary = f"{len(verdicts) - len(unhealthy)}/{len(verdicts)} healthy"
        detail = ", ".join(f"{v.name} {v.health.value}" for v in unhealthy[:5])
        rows.append(["jobs", summary, detail])
    else:
        rows.append(["jobs", "ERROR", result.jobs.error or ""])

    if result.checks.ok and result.checks.value is not None:
        checks = result.checks.value
        bad = failing(checks)
        detail = ", ".join(f"{check.node}/{check.name}" for check in bad[:5])
        rows.append(["consul", f"{len(bad)} failing of {len(checks)}", detail])
    else:
        rows.append(["consul", "ERROR", result.checks.error or ""])

    table("cluster status", ["source", "state", "detail"], rows, footer=CONSUL_FILTER_FOOTER)
