"""`localstack service`: what the edge serves, what runs it, and is it healthy.

Three sources that share no key, joined honestly. The disagreements are the
output: a routed hostname with no job behind it, a job with no route, a job
whose Consul check is missing. An inner join would drop every one of those,
which are the rows you actually opened this for.
"""

import webbrowser

import typer

from localstack_cli.api import consul, haproxy, nomad, services
from localstack_cli.api.errors import ClusterError
from localstack_cli.commands._common import fail, refreshed_session, require_session, warn
from localstack_cli.commands._session import explain
from localstack_cli.commands.render import CONSUL_FILTER_FOOTER, emit_json, table
from localstack_cli.config import Config, ConfigError

app = typer.Typer()

# The job that renders the edge config, and the template inside it that holds
# the routing table.
EDGE_JOB = "haproxy"
EDGE_CONFIG = "local/haproxy.cfg"


@app.command()
def service(
    name: str | None = typer.Argument(None, help="One route name or job id."),
    open_it: bool = typer.Option(False, "--open", help="Open the URL in a browser."),
    as_json: bool = typer.Option(False, "--json", help="Emit the result as JSON."),
) -> None:
    """Show every routed service, what runs it and whether it is healthy."""
    try:
        config = Config.from_env()
    except ConfigError as error:
        raise fail(str(error)) from error

    session = refreshed_session(require_session())
    entry = session.credential("nomad_manage")
    token = entry.token if entry else None

    try:
        rows = _collect(config, token)
    except ClusterError as error:
        vault_entry = session.credential("vault")
        raise explain(
            error,
            config.vault_addr,
            vault_entry.token if vault_entry else None,
            nomad_addr=config.nomad_addr,
            nomad_token=token,
        ) from error

    if name is not None:
        found = services.find(rows, name)
        if found is None:
            raise fail(f"no route or job called {name!r}.")
        row, matched = found
        rows = [row]
        warn(f"matched {name!r} as a {matched}.")

        if open_it:
            _open(row.url)

    if as_json:
        emit_json(rows)
        return

    table(
        "services",
        ["name", "url", "job", "source", "health", "backend"],
        [[r.name, r.url, r.job, r.job_source.value, r.health, r.backend] for r in rows],
        footer=CONSUL_FILTER_FOOTER,
    )


def _collect(config: Config, token: str | None) -> list[services.ServiceRow]:
    """Fetch the three sources and join them."""
    templates = nomad.job_templates(config.nomad_addr, token, EDGE_JOB)
    edge = next((t for t in templates if t.dest_path == EDGE_CONFIG), None)
    if edge is None:
        raise fail(f"the {EDGE_JOB} job carries no {EDGE_CONFIG} template.")

    # Only the parsed routes cross this line. The config text holds a live
    # basic-auth password and is not stored, returned or logged.
    routes = haproxy.parse_routes(edge.text)

    jobs = nomad.job_statuses(config.nomad_addr, token)
    checks = consul.list_checks(config.consul_addr)
    # The catalog, not the checks, is what says a Consul service exists.
    catalog = consul.list_services(config.consul_addr)

    # Service names come from each routed job's own spec rather than being
    # guessed from its id, so the health column cannot be confidently wrong.
    names = {}
    for route in routes:
        if any(job.name == route.name for job in jobs):
            names[route.name] = nomad.job_service_names(config.nomad_addr, token, route.name)

    return services.join(routes, jobs, checks, names, catalog=catalog)


def _open(url: str) -> None:
    """Print the URL, then try to open it.

    In this order, deliberately. Inside a devcontainer the browser launch is
    the part most likely to fail, and a command that opens nothing and prints
    nothing leaves the developer with no way to reach the service.
    """
    if not url:
        warn("no URL for that row.")
        return
    print(url)
    try:
        webbrowser.open(url)
    except Exception as error:  # noqa: BLE001
        warn(f"could not open a browser: {error}. The URL is above.")
