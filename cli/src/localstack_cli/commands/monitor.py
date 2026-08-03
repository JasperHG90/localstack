"""`localstack monitor`: the live panel.

Four things on one screen: Vault seal state, node status, per-job allocation
health, and failing Consul checks. Not a Grafana replacement. Grafana,
Prometheus and Loki already run here and own metrics, history and logs. This
is the terminal glance that answers "is the cluster fine and is my job
running" without opening a browser.

Addresses come from `config.py`, and the values that work are the HTTPS edge
hostnames. The plaintext LAN ports are being closed.
"""

import typer

from localstack_cli.commands._common import fail, refreshed_session, require_session
from localstack_cli.config import Config, ConfigError

app = typer.Typer()


@app.command()
def monitor(
    refresh: float = typer.Option(
        5.0,
        "--refresh",
        help="Seconds between refreshes. 0 refreshes only when you press r.",
    ),
) -> None:
    """Watch the cluster: Vault, nodes, jobs and Consul checks."""
    from localstack_cli.tui.monitor import build

    try:
        config = Config.from_env()
    except ConfigError as error:
        raise fail(str(error)) from error

    # The Nomad reads need a token; the Vault and Consul ones do not. Auth
    # comes entirely from the session `login` brokered: no token is acquired,
    # read from a file, or taken from the environment here.
    # Refreshed the way `env` and `token` do it: the panel is left open for a
    # long time, so starting on a token that is already near expiry would
    # turn every Nomad row into "not authenticated" minutes later.
    session = refreshed_session(require_session())
    entry = session.credential("nomad")

    build(
        vault_addr=config.vault_addr,
        nomad_addr=config.nomad_addr,
        consul_addr=config.consul_addr,
        nomad_token=entry.token if entry else None,
        refresh_seconds=refresh,
    ).run()
