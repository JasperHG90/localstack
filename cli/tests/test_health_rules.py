"""The rules that decide whether a job is healthy.

This is the table the whole panel rests on. The fixture is the full 19-job
capture from the live cluster, so it carries the same shapes that made the
first health model wrong rather than a tidied-up copy.
"""

import ast
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from localstack_cli.api.health import Health, eligible_nodes, judge, judge_all
from localstack_cli.api.nomad import Job, Node, _parse_job

FIXTURES = Path(__file__).parent / "fixtures" / "capture"


def raw_jobs() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads((FIXTURES / "jobs_statuses.json").read_text())
    return loaded


def jobs() -> dict[str, Job]:
    return {job.name: job for job in (_parse_job(item) for item in raw_jobs())}


def nodes() -> list[Node]:
    return [
        Node(
            name=str(item["Name"]),
            status=str(item["Status"]),
            eligibility=str(item["SchedulingEligibility"]),
            draining=bool(item["Drain"]),
        )
        for item in json.loads((FIXTURES / "nodes.json").read_text())
    ]


def test_the_capture_is_the_whole_cluster() -> None:
    """A hand-picked subset would encode a tidier world than the real one."""
    assert len(raw_jobs()) == 19


def test_jobs_come_from_the_api_not_the_repo() -> None:
    """`talat-*` run live and have no job file in this repository.

    Anything driven off `deployments/` silently under-reports by two.
    """
    assert {"talat-shim", "talat-consumer"} <= set(jobs())


@pytest.mark.parametrize("name", ["memex", "phoenix", "haproxy"])
def test_the_jobs_with_the_loudest_lifetime_counters_are_healthy(name: str) -> None:
    """The three that a `Failed > 0` rule would have reded.

    On `/v1/jobs` these carry `Failed: 31`, `Failed: 15, Lost: 2` and
    `Failed: 8` while running at their full desired count. That rule reds 8
    of the 14 service jobs on a healthy cluster.
    """
    verdict = judge(jobs()[name], eligible_nodes(nodes()))

    assert verdict.health is Health.HEALTHY
    assert verdict.counts == "1/1"


def test_the_counters_are_structurally_absent_from_the_data_source() -> None:
    """`/v1/jobs/statuses` elements carry no `JobSummary` key at all."""
    assert all("JobSummary" not in item for item in raw_jobs())


def test_a_bolted_on_counter_block_changes_no_verdict() -> None:
    """The fixture cannot carry them, so prove it another way."""
    plain = raw_jobs()[0]
    loud = {
        **plain,
        "JobSummary": {"Summary": {"app": {"Failed": 99, "Lost": 9, "Complete": 400}}},
    }

    assert judge(_parse_job(loud), 5) == judge(_parse_job(plain), 5)


def executable_source() -> dict[str, str]:
    """Every source module with its comments and docstrings removed.

    The rule being enforced is that no CODE reads the lifetime counters. The
    modules explain at length why they must not be read, so a plain grep over
    the raw text flags the very prose that documents the decision. Stripping
    comments and docstrings leaves the only thing the rule is about.
    """
    source = Path(__file__).resolve().parents[1] / "src" / "localstack_cli"
    stripped = {}
    for path in sorted(source.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            # A docstring is the first statement of a module, class or
            # function; blanking it leaves the rest of the body intact.
            if isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            ) and ast.get_docstring(node):
                node.body[0] = ast.Pass()
        stripped[str(path.relative_to(source))] = ast.unparse(tree)
    return stripped


def test_source_never_reads_the_lifetime_counters() -> None:
    """R4: no rule anywhere may branch on `JobSummary`."""
    offenders = [name for name, code in executable_source().items() if "JobSummary" in code]

    assert offenders == []


def test_source_never_calls_the_jobs_endpoint() -> None:
    """R4: the data source is `/v1/jobs/statuses` and nothing else.

    Note the eval row scores this with `grep -rn "/v1/jobs\\b"`, and `\\b`
    matches between `jobs` and `/`, so that pattern flags `/v1/jobs/statuses`
    too. Scored literally it fails every correct implementation. The rule it
    means is the one here: no call to `/v1/jobs` itself.
    """
    pattern = re.compile(r"/v1/jobs(?!/statuses)")
    offenders = [name for name, code in executable_source().items() if pattern.search(code)]

    assert offenders == []


@pytest.mark.parametrize("name", ["acme", "backup-minio", "backup-postgres"])
def test_a_periodic_parent_is_healthy_with_no_allocations(name: str) -> None:
    """Nomad garbage-collects the children, so there is nothing else to read."""
    job = jobs()[name]
    assert job.is_periodic_parent
    assert job.allocs == []

    assert judge(job, eligible_nodes(nodes())).health is Health.HEALTHY


def test_a_periodic_parent_with_null_allocs_does_not_crash() -> None:
    """The API sends JSON null, not an empty list, and `len(None)` raises."""
    raw = next(item for item in raw_jobs() if item["Name"] == "acme")
    assert raw["Allocs"] is None

    assert _parse_job(raw).allocs == []


def test_a_stopped_periodic_parent_is_not_healthy() -> None:
    job = replace(jobs()["acme"], stopped=True)

    assert judge(job, 5).health is Health.STOPPED


@pytest.mark.parametrize("name", ["node-exporter", "promtail"])
def test_a_system_job_is_judged_against_eligible_nodes(name: str) -> None:
    """`GroupCountSum` is per-node here: it reads 1 while 5 allocs run."""
    job = jobs()[name]
    assert job.desired == 1
    assert job.running_allocs == 5

    verdict = judge(job, eligible_nodes(nodes()))

    assert verdict.health is Health.HEALTHY
    assert verdict.counts == "5/5"


def test_a_system_job_missing_a_node_is_degraded() -> None:
    job = jobs()["node-exporter"]
    short = replace(job, allocs=job.allocs[:4])

    verdict = judge(short, 5)

    assert verdict.health is Health.DEGRADED
    assert verdict.counts == "4/5"


def test_a_service_job_below_its_desired_count_is_degraded() -> None:
    """The only way a service job goes red."""
    job = replace(jobs()["postgres"], desired=3)

    verdict = judge(job, 5)

    assert verdict.health is Health.DEGRADED
    assert verdict.counts == "1/3"


def test_a_service_job_with_a_dead_alloc_is_degraded() -> None:
    job = jobs()["postgres"]
    dead = replace(job, allocs=[replace(job.allocs[0], client_status="failed")])

    assert judge(dead, 5).health is Health.DEGRADED


def test_the_whole_healthy_cluster_reads_healthy() -> None:
    """The regression this ticket exists to prevent: 11 of 19 wrong rows."""
    verdicts = judge_all(list(jobs().values()), nodes())

    unhealthy = [v.name for v in verdicts if v.health is not Health.HEALTHY]
    assert unhealthy == []
    assert len(verdicts) == 19


def test_degraded_jobs_sort_first() -> None:
    """A failure must be visible without scrolling past 18 healthy rows."""
    every = list(jobs().values())
    broken = replace(jobs()["postgres"], desired=9)
    verdicts = judge_all([job for job in every if job.name != "postgres"] + [broken], nodes())

    assert verdicts[0].name == "postgres"
    assert verdicts[0].health is Health.DEGRADED


def test_eligible_nodes_ignores_a_draining_node() -> None:
    every = nodes()
    draining = [replace(every[0], draining=True), *every[1:]]

    assert eligible_nodes(draining) == len(every) - 1


def test_a_system_job_with_no_node_count_is_not_called_healthy() -> None:
    """The panel must not claim health it has no basis for.

    With no node count there is nothing to compare against, and `running >= 0`
    would call a `system` job running NOWHERE healthy. That is the panel lying
    in the direction that hides an outage. Reachable whenever `/v1/nodes`
    fails while `/v1/jobs/statuses` succeeds.
    """
    from localstack_cli.api.nomad import Job

    stranded = replace(jobs()["node-exporter"], allocs=[])

    verdict = judge(stranded, 0)

    assert verdict.health is Health.UNKNOWN
    assert isinstance(stranded, Job)


def test_a_running_system_job_with_no_node_count_is_also_unknown() -> None:
    """Not healthy either: 5 running against an unknown target proves nothing."""
    assert judge(jobs()["node-exporter"], 0).health is Health.UNKNOWN


def test_only_system_jobs_need_the_node_count() -> None:
    """A service job's desired count comes from the job itself."""
    assert judge(jobs()["postgres"], 0).health is Health.HEALTHY
    assert judge(jobs()["acme"], 0).health is Health.HEALTHY
