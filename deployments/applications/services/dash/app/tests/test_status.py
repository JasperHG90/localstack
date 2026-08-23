import pytest
from localstack_cli.api.consul import Check
from localstack_cli.api.health import Health
from localstack_cli.api.nomad import Alloc, Job, Node

from dash_app.status import compute_tile_states, status_for
from dash_app.tiles import Tile


def _tile(key: str, job: str, category: str = "dashboard") -> Tile:
    return Tile(
        key=key,
        name=key,
        desc="",
        color="#000000",
        icon="",
        category=category,  # type: ignore[arg-type]
        job=job,
        node="test-node",
        url="https://example.lab.orangecluster.nl" if category == "dashboard" else None,
    )


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


def test_a_tile_with_no_matching_job_is_unknown_not_a_guess() -> None:
    tiles = [_tile("grafana", "grafana")]
    # No job named "grafana" in the fake job list -- it was renamed or removed.
    jobs: list[Job] = [
        Job(name="other-job", job_type="service", status="running", stopped=False, desired=1),
    ]

    states = compute_tile_states(tiles, jobs, nodes=[], checks=[], catalog={}, service_names={})

    assert states[0].status == "unknown"


def test_a_healthy_service_job_reports_up() -> None:
    tiles = [_tile("grafana", "grafana")]
    jobs = [
        Job(
            name="grafana",
            job_type="service",
            status="running",
            stopped=False,
            desired=1,
            allocs=[Alloc(client_status="running", group="grafana", node_id="n1")],
        ),
    ]

    states = compute_tile_states(tiles, jobs, nodes=[], checks=[], catalog={}, service_names={})

    assert states[0].status == "up"
    assert states[0].counts == "1/1"


def test_an_under_replicated_service_job_reports_degraded() -> None:
    tiles = [_tile("phoenix", "phoenix")]
    jobs = [
        Job(name="phoenix", job_type="service", status="running", stopped=False, desired=1),
    ]

    states = compute_tile_states(tiles, jobs, nodes=[], checks=[], catalog={}, service_names={})

    assert states[0].status == "degraded"


def test_a_stopped_job_reports_down() -> None:
    tiles = [_tile("loki", "loki")]
    jobs = [
        Job(name="loki", job_type="service", status="dead", stopped=True, desired=1),
    ]

    states = compute_tile_states(tiles, jobs, nodes=[], checks=[], catalog={}, service_names={})

    assert states[0].status == "down"


def test_an_agent_endpoint_tile_falls_back_to_consul_check_state() -> None:
    tiles = [_tile("vault", "vault")]
    # No Nomad job named "vault" -- it runs as a host agent, not a Nomad job.
    checks = [Check(name="vault-agent", status="passing", node="firebat", service="vault")]
    catalog: dict[str, list[str]] = {"vault": []}

    states = compute_tile_states(
        tiles, jobs=[], nodes=[], checks=checks, catalog=catalog, service_names={}
    )

    assert states[0].status == "up"


def test_a_node_argument_change_never_touches_dashboard_tile_matching() -> None:
    """Regression guard: node list only feeds `eligible_nodes` for system jobs."""
    tiles = [_tile("grafana", "grafana")]
    jobs = [
        Job(
            name="grafana",
            job_type="service",
            status="running",
            stopped=False,
            desired=1,
            allocs=[Alloc(client_status="running", group="grafana", node_id="n1")],
        ),
    ]
    nodes = [Node(name="ubuntu", status="ready", eligibility="eligible", draining=False)]

    states = compute_tile_states(tiles, jobs, nodes, checks=[], catalog={}, service_names={})

    assert states[0].status == "up"
