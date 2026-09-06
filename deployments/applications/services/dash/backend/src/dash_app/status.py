"""Map this app's own health/join results onto tile status.

Calls `dash_app.health.judge_all` and `dash_app.services.join` directly --
this app's own copies of the pure functions `cli`'s `localstack service`
command uses (see `cli/src/localstack_cli/commands/service.py:79-102`),
copied down rather than imported so the backend carries no runtime
dependency on `cli` at all (Requirement 2). This app never shells out to
the `localstack` CLI itself: every read command hard-requires a session
file from an interactive human Vault login
(`cli/src/localstack_cli/commands/_common.py:26-34`), which a Nomad job has
no way to hold.

One deliberate difference from that command's own `_collect`: this app never
reads HAProxy's own job spec to build a route table. That spec embeds a live
credential in plaintext (see cli's `api/haproxy.py` docstring), and nothing
here needs it -- every tile already names its own Nomad jobs explicitly in
`tiles.json`. Instead, one synthetic `Route` is built per JOB, named after
that job, so `join()`'s existing resolution ladder (job id, then Consul
service name) still does the matching, just without ever fetching a real
routing table. A tile naming two jobs resolves each one separately and
folds the results. See `worst`.
"""

from __future__ import annotations

from dataclasses import dataclass

from dash_app.consul_client import Check
from dash_app.health import Health, JobHealth
from dash_app.health import judge_all as judge_all
from dash_app.nomad_client import Job, Node
from dash_app.services import JobSource, Route, ServiceRow
from dash_app.services import join as join
from dash_app.tiles import Group, JobRef, Tile

TileStatus = str  # "up" | "degraded" | "down" | "unknown"

_HEALTH_TO_STATUS: dict[Health, TileStatus] = {
    Health.HEALTHY: "up",
    Health.DEGRADED: "degraded",
    Health.STOPPED: "down",
    Health.UNKNOWN: "unknown",
}


# Ranked worst-last. `worst` folds a tile's jobs through this, and
# `unknown` outranks `up` because absence of a signal is not evidence of
# health -- the stance `services.NO_CHECK` already takes.
_SEVERITY: dict[TileStatus, int] = {"up": 0, "unknown": 1, "degraded": 2, "down": 3}


def worst(statuses: list[TileStatus]) -> TileStatus:
    """The worst status in the list, or "unknown" for an empty list."""
    if not statuses:
        return "unknown"
    return max(statuses, key=lambda status: _SEVERITY[status])


@dataclass(frozen=True)
class JobState:
    """One job behind a tile, resolved on its own."""

    job: JobRef
    status: TileStatus
    counts: str
    checks: str


@dataclass(frozen=True)
class TileState:
    """A tile's live status, ready to render.

    `node` and `counts` are the DECIDING job's: the worst-severity one,
    ties broken by config order. For a one-job tile that is just that
    job's; for a two-job tile it names where the problem actually is.
    """

    tile: Tile
    status: TileStatus
    node: str
    counts: str
    jobs: list[JobState]


@dataclass(frozen=True)
class GroupState:
    """One headed section, with its tiles in config order."""

    group: Group
    tiles: list[TileState]


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
    "critical"). Only used for an agent endpoint (Vault, Nomad, Consul),
    which carries no Nomad job for `judge_all` to assess.

    "no check" only reaches here already carrying `JobSource.CONSUL_NAME`
    (`_job_state` calls this function only in that branch): join() has
    already confirmed the job name is a real service in Consul's own
    catalog, it just has no check registered against it --
    Consul's own agent is the standing example, since its only check
    (`serfHealth`) carries no `ServiceName` (`consul_client.py`'s own
    docstring). Catalog presence is itself the health signal here, so this
    reads "up", not "unknown". "not found" is kept distinct and still
    unknown: it means join() could not confirm the tile in Consul's
    catalog at all, a strictly weaker signal than "no check".
    """
    if check_state in ("passing", "no check"):
        return "up"
    if check_state == "not found":
        return "unknown"
    return "down"


def build_routes(groups: list[Group]) -> list[Route]:
    """One synthetic `Route` per job, named after that job.

    De-duplicated by name, because two tiles may name the same job.
    `hostname`/`backend_host`/`backend_port` are left blank, because
    `join()`'s health computation reads only `route.name`.
    """
    names = dict.fromkeys(job.name for group in groups for tile in group.tiles for job in tile.jobs)
    return [Route(name=name, hostname="", backend_host="", backend_port=0) for name in names]


def _job_state(
    job: JobRef,
    healths_by_job: dict[str, JobHealth],
    rows_by_name: dict[str, ServiceRow],
) -> JobState:
    """Resolve one job on the same three-rung ladder as before.

    `judge_all` is the primary signal for a real Nomad job. A job with no
    such entry (an agent endpoint like Vault, Nomad or Consul) falls back
    to `join()`'s Consul-check resolution instead.
    """
    job_health = healths_by_job.get(job.name)
    row = rows_by_name.get(job.name)

    if job_health is not None:
        status = status_for(job_health.health)
        counts = job_health.counts
    elif row is not None and row.job_source is JobSource.CONSUL_NAME:
        status = _status_from_consul(row.health)
        counts = ""
    else:
        status = "unknown"
        counts = ""

    checks = row.health if row is not None else ""
    return JobState(job=job, status=status, counts=counts, checks=checks)


def _tile_state(tile: Tile, job_states: list[JobState]) -> TileState:
    deciding = max(job_states, key=lambda state: _SEVERITY[state.status])
    return TileState(
        tile=tile,
        status=worst([state.status for state in job_states]),
        node=deciding.job.node,
        counts=deciding.counts,
        jobs=job_states,
    )


def compute_tile_states(
    groups: list[Group],
    jobs: list[Job],
    nodes: list[Node],
    checks: list[Check],
    catalog: dict[str, list[str]],
    service_names: dict[str, list[str]],
) -> list[GroupState]:
    """One `GroupState` per configured group, in config order."""
    healths_by_job = {h.name: h for h in judge_all(jobs, nodes)}
    routes = build_routes(groups)
    rows_by_name = {
        row.name: row for row in join(routes, jobs, checks, service_names, catalog=catalog)
    }

    return [
        GroupState(
            group=group,
            tiles=[
                _tile_state(
                    tile,
                    [_job_state(job, healths_by_job, rows_by_name) for job in tile.jobs],
                )
                for tile in group.tiles
            ],
        )
        for group in groups
    ]


def unknown_states(groups: list[Group]) -> list[GroupState]:
    """The page's shape with nothing known yet, for a failed fetch."""
    return [
        GroupState(
            group=group,
            tiles=[
                _tile_state(
                    tile,
                    [
                        JobState(job=job, status="unknown", counts="", checks="")
                        for job in tile.jobs
                    ],
                )
                for tile in group.tiles
            ],
        )
        for group in groups
    ]
