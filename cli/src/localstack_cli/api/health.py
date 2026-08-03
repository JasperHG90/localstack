"""Is this job actually healthy?

Pure functions over `nomad.Job`, so the rule table is a unit test rather than
a snapshot. This is the part of the panel most able to lie, and a panel that
reds a healthy cluster gets ignored and then misses the real outage.

Three job types, three rules, all from one `/v1/jobs/statuses` response:

- `service`: running allocations against `GroupCountSum`. Below it is
  degraded. This is the only way a service job goes red.
- `system`: running allocations against the number of ELIGIBLE NODES.
  `GroupCountSum` is per-node here and reads 1 while five allocations run,
  so comparing against it would red every system job.
- `batch` periodic parent: healthy when `Status == "running"` and not
  stopped, and on nothing else. Nomad garbage-collects the children, so a
  healthy parent has no allocations and an empty `ChildStatuses`; judging on
  either reds all three parents here.

No rule reads a lifetime counter. `/v1/jobs/statuses` does not carry them.
"""

from dataclasses import dataclass
from enum import Enum

from localstack_cli.api.nomad import Job, Node


class Health(Enum):
    """What the panel shows for one job."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    # A `system` job cannot be judged without a node count, and the node
    # fetch can fail or not have landed yet. Saying "healthy" there would be
    # a claim the panel has no basis for, and it is the direction that hides
    # an outage rather than inventing one.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class JobHealth:
    """A job's verdict, plus the counts the panel renders beside it."""

    name: str
    job_type: str
    health: Health
    running: int
    expected: int

    @property
    def counts(self) -> str:
        return f"{self.running}/{self.expected}"


def eligible_nodes(nodes: list[Node]) -> int:
    """How many nodes a `system` job should be running on."""
    return sum(1 for node in nodes if node.usable)


def judge(job: Job, eligible: int) -> JobHealth:
    """One job's verdict. `eligible` only matters for `system` jobs."""
    if job.stopped:
        return JobHealth(job.name, job.job_type, Health.STOPPED, job.running_allocs, job.desired)

    if job.is_periodic_parent:
        # No allocations and no children is the healthy resting state, so the
        # parent's own status is the only honest signal.
        healthy = job.status == "running"
        expected = 0
        return JobHealth(
            job.name,
            job.job_type,
            Health.HEALTHY if healthy else Health.DEGRADED,
            0,
            expected,
        )

    running = job.running_allocs

    if job.job_type == "system":
        if eligible <= 0:
            # No node count, so there is nothing to compare against. With
            # `running >= 0` this would read HEALTHY for a system job running
            # nowhere, which is the panel lying in the worst direction.
            return JobHealth(job.name, job.job_type, Health.UNKNOWN, running, eligible)
        expected = eligible
    else:
        expected = job.desired

    healthy = running >= expected and job.status == "running"
    return JobHealth(
        job.name,
        job.job_type,
        Health.HEALTHY if healthy else Health.DEGRADED,
        running,
        expected,
    )


def judge_all(jobs: list[Job], nodes: list[Node]) -> list[JobHealth]:
    """Every job's verdict, degraded ones first so a failure needs no scroll."""
    eligible = eligible_nodes(nodes)
    verdicts = [judge(job, eligible) for job in jobs]
    return sorted(verdicts, key=lambda v: (v.health is Health.HEALTHY, v.name))
