"""Map cli's health/join results onto tile status.

Calls `localstack_cli.api.health.judge_all` and `localstack_cli.api.services.join`
directly -- the same tested, pure functions the `localstack service` command
already uses (see `cli/src/localstack_cli/commands/service.py:79-102`). This
app never shells out to the `localstack` CLI itself: every read command hard
-requires a session file from an interactive human Vault login
(`cli/src/localstack_cli/commands/_common.py:26-34`), which a Nomad job has
no way to hold.

One deliberate difference from that command's own `_collect`: this app never
reads HAProxy's own job spec to build a route table. That spec embeds a live
credential in plaintext (see cli's `api/haproxy.py` docstring), and nothing
here needs it -- every tile already names its own Nomad job explicitly in
`tiles.json`. Instead, one synthetic `Route` is built per tile, named after
its job, so `join()`'s existing resolution ladder (job id, then Consul
service name) still does the matching, just without ever fetching a real
routing table.
"""

from __future__ import annotations

from dataclasses import dataclass

from localstack_cli.api.consul import Check
from localstack_cli.api.haproxy import Route
from localstack_cli.api.health import Health
from localstack_cli.api.health import judge_all as judge_all
from localstack_cli.api.nomad import Job, Node
from localstack_cli.api.services import JobSource
from localstack_cli.api.services import join as join

from dash_app.tiles import Tile

TileStatus = str  # "up" | "degraded" | "down" | "unknown"

_HEALTH_TO_STATUS: dict[Health, TileStatus] = {
    Health.HEALTHY: "up",
    Health.DEGRADED: "degraded",
    Health.STOPPED: "down",
    Health.UNKNOWN: "unknown",
}


@dataclass(frozen=True)
class TileState:
    """A tile's live status, ready to render."""

    tile: Tile
    status: TileStatus
    counts: str
    checks: str


def status_for(health: Health) -> TileStatus:
    """The tile-facing status word for one `Health` value.

    A dict lookup, not a chain of `if`s, so a `Health` value this map
    forgets to cover raises `KeyError` instead of silently defaulting to
    "up" -- the failure direction that hides a real outage.
    """
    return _HEALTH_TO_STATUS[health]


def _status_from_consul(check_state: str) -> TileStatus:
    """The tile-facing status word for a Consul check-state string.

    `check_state` is `_check_state`'s own vocabulary: "passing", "no
    check", "not found", or a joined set of failing statuses (e.g.
    "critical"). Only used for agent-endpoint tiles (Vault, Nomad,
    Consul), which carry no Nomad job for `judge_all` to assess.
    """
    if check_state == "passing":
        return "up"
    if check_state in ("no check", "not found"):
        return "unknown"
    return "down"


def build_routes(tiles: list[Tile]) -> list[Route]:
    """One synthetic `Route` per tile, named after its job.

    `hostname`/`backend_host`/`backend_port` are left blank: `join()`'s
    health computation reads only `route.name` to match a job or a
    Consul service name, never those fields.
    """
    return [Route(name=tile.job, hostname="", backend_host="", backend_port=0) for tile in tiles]


def compute_tile_states(
    tiles: list[Tile],
    jobs: list[Job],
    nodes: list[Node],
    checks: list[Check],
    catalog: dict[str, list[str]],
    service_names: dict[str, list[str]],
) -> list[TileState]:
    """One `TileState` per configured tile.

    `judge_all` is the primary signal for a tile backed by a real Nomad
    job. A tile with no such job (an agent endpoint like Vault, Nomad or
    Consul) falls back to `join()`'s Consul-check resolution instead.
    """
    healths_by_job = {h.name: h for h in judge_all(jobs, nodes)}
    routes = build_routes(tiles)
    rows_by_name = {
        row.name: row for row in join(routes, jobs, checks, service_names, catalog=catalog)
    }

    states = []
    for tile in tiles:
        job_health = healths_by_job.get(tile.job)
        row = rows_by_name.get(tile.job)

        if job_health is not None:
            status = status_for(job_health.health)
            counts = job_health.counts
        elif row is not None and row.job_source is JobSource.CONSUL_NAME:
            status = _status_from_consul(row.health)
            counts = ""
        else:
            status = "unknown"
            counts = ""

        states.append(
            TileState(
                tile=tile,
                status=status,
                counts=counts,
                checks=row.health if row is not None else "",
            )
        )
    return states
