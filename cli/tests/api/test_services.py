"""The outer join. An inner one would hide every row worth looking at."""

from localstack_cli.api.consul import Check
from localstack_cli.api.haproxy import Route
from localstack_cli.api.nomad import Job
from localstack_cli.api.services import (
    AGENT_ENDPOINT,
    NO_CHECK,
    NOT_FOUND,
    JobSource,
    ServiceRow,
    find,
    join,
)


def route(name: str, port: int = 8080) -> Route:
    return Route(
        name=name, hostname=f"{name}.lab.example", backend_host="10.0.0.1", backend_port=port
    )


def job(name: str) -> Job:
    return Job(name=name, job_type="service", status="running", stopped=False, desired=1)


def check(service: str, status: str = "passing") -> Check:
    return Check(name=f"{service}-check", status=status, node="firebat", service=service)


ROUTES = [route("memex"), route("vault"), route("s3", 9000)]
JOBS = [job("memex"), job("hermes")]
CHECKS = [check("memex"), check("vault")]
NAMES = {"memex": ["memex"]}


def rows_by_name() -> dict[str, ServiceRow]:
    return {row.name: row for row in join(ROUTES, JOBS, CHECKS, NAMES)}


def test_all_four_join_cases_render() -> None:
    """Route-with-job, route-via-consul, route-with-neither, job-with-no-route."""
    rows = rows_by_name()

    assert set(rows) == {"memex", "vault", "s3", "hermes"}


def test_a_route_matching_a_job_id_resolves_by_job_id() -> None:
    row = rows_by_name()["memex"]

    assert row.job_source is JobSource.JOB_ID
    assert row.job == "memex"
    assert row.health == "passing"
    assert row.url == "https://memex.lab.example"


def test_an_agent_endpoint_resolves_by_consul_name() -> None:
    """`vault`, `nomad` and `consul` are backed by no Nomad job at all."""
    row = rows_by_name()["vault"]

    assert row.job_source is JobSource.CONSUL_NAME
    assert row.job == AGENT_ENDPOINT
    assert row.health == "passing"


def test_a_route_resolving_to_neither_still_renders() -> None:
    """`s3` is the live example. Rendering it is correct output, not a bug."""
    row = rows_by_name()["s3"]

    assert row.job_source is JobSource.UNRESOLVED
    assert row.job == NOT_FOUND
    assert row.health == NOT_FOUND
    assert row.backend == "10.0.0.1:9000"
    assert row.url == "https://s3.lab.example"


def test_a_job_with_no_route_renders_with_an_empty_url() -> None:
    row = rows_by_name()["hermes"]

    assert row.job_source is JobSource.NO_ROUTE
    assert row.url == ""
    assert row.job == "hermes"


def test_a_job_with_no_check_is_not_called_healthy() -> None:
    """Absence of a check is not evidence of health."""
    assert rows_by_name()["hermes"].health == NO_CHECK


def test_a_failing_check_shows_its_status() -> None:
    rows = {row.name: row for row in join(ROUTES, JOBS, [check("memex", "critical")], NAMES)}

    assert rows["memex"].health == "critical"


def test_health_follows_the_jobs_own_service_name_not_its_id() -> None:
    """Guessing the service name from the job id renders confident nonsense."""
    renamed = {"memex": ["memex-web"]}
    checks = [check("memex-web")]

    rows = {row.name: row for row in join(ROUTES, JOBS, checks, renamed)}

    assert rows["memex"].health == "passing"


def test_a_job_whose_service_is_unknown_reports_no_check() -> None:
    rows = {row.name: row for row in join(ROUTES, JOBS, CHECKS, {})}

    assert rows["memex"].health == NO_CHECK


def test_consul_is_a_column_never_a_row_key() -> None:
    """A Consul service that is neither routed nor a job must not add a row."""
    checks = [*CHECKS, check("something-only-consul-knows")]

    rows = {row.name for row in join(ROUTES, JOBS, checks, NAMES)}

    assert "something-only-consul-knows" not in rows


def test_every_route_and_every_job_appears() -> None:
    rows = join(ROUTES, JOBS, CHECKS, NAMES)

    assert len(rows) == len({r.name for r in ROUTES} | {j.name for j in JOBS})


def test_find_matches_a_route_name_first() -> None:
    rows = join(ROUTES, JOBS, CHECKS, NAMES)

    found = find(rows, "memex")

    assert found is not None
    assert found[1] == "route"


def test_find_falls_back_to_a_job_id() -> None:
    rows = join(ROUTES, JOBS, CHECKS, NAMES)

    found = find(rows, "hermes")

    assert found is not None
    assert found[1] == "job"


def test_find_returns_nothing_for_an_unknown_name() -> None:
    assert find(join(ROUTES, JOBS, CHECKS, NAMES), "nope") is None
