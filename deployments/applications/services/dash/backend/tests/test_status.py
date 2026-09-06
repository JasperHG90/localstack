import pytest

from dash_app.consul_client import Check
from dash_app.health import Health
from dash_app.nomad_client import Alloc, Job, Node
from dash_app.status import (
    GroupState,
    compute_tile_states,
    status_for,
    unknown_states,
    worst,
)
from dash_app.tiles import FrontEnd, Group, JobRef, Tile


def _tile(key: str, *jobs: tuple[str, str]) -> Tile:
    return Tile(
        key=key,
        name=key,
        desc="",
        color="#000000",
        icon="",
        jobs=[JobRef(name=name, node=node) for name, node in (jobs or ((key, "test-node"),))],
        fe=FrontEnd(url="https://example.lab.orangecluster.nl"),
    )


def _groups(*tiles: Tile) -> list[Group]:
    return [Group(key="g", title="G", hint="", tiles=list(tiles))]


def _states(
    groups: list[Group],
    jobs: list[Job] | None = None,
    nodes: list[Node] | None = None,
    checks: list[Check] | None = None,
    catalog: dict[str, list[str]] | None = None,
) -> list[GroupState]:
    return compute_tile_states(
        groups,
        jobs or [],
        nodes or [],
        checks or [],
        catalog or {},
        service_names={},
    )


def _running(name: str) -> Job:
    return Job(
        name=name,
        job_type="service",
        status="running",
        stopped=False,
        desired=1,
        allocs=[Alloc(client_status="running", group=name, node_id="n1")],
    )


def _stopped(name: str) -> Job:
    return Job(name=name, job_type="service", status="dead", stopped=True, desired=0)


@pytest.mark.parametrize(
    ("health", "expected"),
    [
        (Health.HEALTHY, "up"),
        (Health.DEGRADED, "degraded"),
        (Health.STOPPED, "down"),
        (Health.UNKNOWN, "unknown"),
    ],
)
def test_status_for_maps_every_health_value(health: Health, expected: str) -> None:
    assert status_for(health) == expected


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["up", "up"], "up"),
        (["up", "unknown"], "unknown"),
        (["up", "degraded"], "degraded"),
        (["up", "down"], "down"),
        (["unknown", "degraded"], "degraded"),
        (["unknown", "down"], "down"),
        (["degraded", "down"], "down"),
        (["down", "up"], "down"),
    ],
)
def test_worst_ranks_down_over_degraded_over_unknown_over_up(
    statuses: list[str], expected: str
) -> None:
    assert worst(statuses) == expected


def test_groups_and_tiles_come_back_in_config_order() -> None:
    groups = [
        Group(key="one", title="One", hint="", tiles=[_tile("a"), _tile("b")]),
        Group(key="two", title="Two", hint="", tiles=[_tile("c")]),
    ]

    states = _states(groups)

    assert [g.group.key for g in states] == ["one", "two"]
    assert [t.tile.key for t in states[0].tiles] == ["a", "b"]


def test_a_tile_with_no_matching_job_is_unknown_not_a_guess() -> None:
    jobs = [Job(name="other-job", job_type="service", status="running", stopped=False, desired=1)]

    states = _states(_groups(_tile("grafana")), jobs=jobs)

    assert states[0].tiles[0].status == "unknown"


def test_a_single_job_tile_reports_that_jobs_status_and_node() -> None:
    states = _states(_groups(_tile("grafana", ("grafana", "ubuntu"))), jobs=[_running("grafana")])

    tile = states[0].tiles[0]
    assert tile.status == "up"
    assert tile.node == "ubuntu"
    assert [(j.job.name, j.status) for j in tile.jobs] == [("grafana", "up")]


def test_an_under_replicated_service_job_reports_degraded() -> None:
    jobs = [
        Job(
            name="grafana",
            job_type="service",
            status="running",
            stopped=False,
            desired=2,
            allocs=[Alloc(client_status="running", group="grafana", node_id="n1")],
        ),
    ]

    states = _states(_groups(_tile("grafana")), jobs=jobs)

    assert states[0].tiles[0].status == "degraded"


def test_a_stopped_job_reports_down() -> None:
    states = _states(_groups(_tile("grafana")), jobs=[_stopped("grafana")])

    assert states[0].tiles[0].status == "down"


def test_a_two_job_tile_reports_the_worst_of_the_two() -> None:
    """A dead browser view must not hide behind a healthy API."""
    tile = _tile("registry", ("registry", "ubuntu"), ("registry-ui", "radxa-dragon-q6a"))
    jobs = [_running("registry"), _stopped("registry-ui")]

    state = _states(_groups(tile), jobs=jobs)[0].tiles[0]

    assert state.status == "down"
    # The positive control: with both jobs healthy the same tile reads up, so
    # the "down" above comes from the fold and not from a broken lookup.
    healthy = _states(_groups(tile), jobs=[_running("registry"), _running("registry-ui")])
    assert healthy[0].tiles[0].status == "up"


def test_a_two_job_tile_reports_the_deciding_jobs_node_and_counts() -> None:
    tile = _tile("registry", ("registry", "ubuntu"), ("registry-ui", "radxa-dragon-q6a"))
    jobs = [_running("registry"), _stopped("registry-ui")]

    state = _states(_groups(tile), jobs=jobs)[0].tiles[0]

    assert state.node == "radxa-dragon-q6a"
    assert state.counts == next(j.counts for j in state.jobs if j.job.name == "registry-ui")


def test_each_job_of_a_tile_carries_its_own_node() -> None:
    tile = _tile("registry", ("registry", "ubuntu"), ("registry-ui", "radxa-dragon-q6a"))

    state = _states(_groups(tile), jobs=[_running("registry"), _running("registry-ui")])[0].tiles[0]

    assert [(j.job.name, j.job.node) for j in state.jobs] == [
        ("registry", "ubuntu"),
        ("registry-ui", "radxa-dragon-q6a"),
    ]


def test_an_agent_endpoint_tile_falls_back_to_consul_check_state() -> None:
    # No Nomad job named "vault" -- it runs as a host agent, not a Nomad job.
    checks = [Check(name="vault-agent", status="passing", node="firebat", service="vault")]

    states = _states(_groups(_tile("vault")), checks=checks, catalog={"vault": []})

    assert states[0].tiles[0].status == "up"


def test_an_agent_endpoint_tile_with_no_registered_check_still_reports_up() -> None:
    """Consul's own agent is the standing example: it registers itself in
    the catalog, but its only check (serfHealth) carries no ServiceName, so
    no check is ever found for it. Catalog presence alone is the health
    signal for an agent endpoint, not "unknown"."""
    states = _states(_groups(_tile("consul")), catalog={"consul": []})

    assert states[0].tiles[0].status == "up"


def test_a_node_argument_change_never_touches_tile_matching() -> None:
    """Regression guard: node list only feeds `eligible_nodes` for system jobs."""
    nodes = [Node(name="ubuntu", status="ready", eligibility="eligible", draining=False)]

    states = _states(_groups(_tile("grafana")), jobs=[_running("grafana")], nodes=nodes)

    assert states[0].tiles[0].status == "up"


def test_unknown_states_keeps_the_shape_but_knows_nothing() -> None:
    groups = [
        Group(key="one", title="One", hint="h", tiles=[_tile("a", ("a", "n1"), ("b", "n2"))]),
    ]

    states = unknown_states(groups)

    assert [g.group.key for g in states] == ["one"]
    tile = states[0].tiles[0]
    assert tile.status == "unknown"
    assert tile.node == "n1"
    assert [j.status for j in tile.jobs] == ["unknown", "unknown"]
