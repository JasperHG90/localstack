"""Join the edge's routes, Nomad's jobs and Consul's checks.

Three sources that share no key, and the disagreement between them is the
answer. An inner join would hide exactly the broken cases someone runs this
command to find, so the join is an outer one over the union of routes and
job ids, and Consul is a column rather than a row key.

Resolving a route to a job goes down a ladder, and which rung answered is
recorded on the row:

- `job-id`: a Nomad job whose id equals the route name. The common case.
- `consul-name`: no such job, but a Consul service by that name. This is how
  `vault`, `nomad` and `consul` resolve; they are agent endpoints backed by
  no Nomad job at all.
- `unresolved`: neither. The row still renders, with the hostname and the raw
  backend, and both other columns marked not found. `s3` is the live example,
  and rendering it that way is correct output rather than a bug.

Missing means missing throughout. A job with no Consul check renders "no
check", never healthy. A route with no job is never dropped.
"""

from dataclasses import dataclass, field
from enum import Enum

from localstack_cli.api.consul import Check
from localstack_cli.api.haproxy import Route
from localstack_cli.api.nomad import Job


class JobSource(Enum):
    """Which rung of the ladder resolved a row."""

    JOB_ID = "job-id"
    CONSUL_NAME = "consul-name"
    UNRESOLVED = "unresolved"
    # A job with no route at all. Thirteen exist live.
    NO_ROUTE = "no-route"


# What the health column says when there is nothing to say. Not "healthy":
# absence of a check is not evidence of health.
NO_CHECK = "no check"
NOT_FOUND = "not found"
AGENT_ENDPOINT = "no job (agent endpoint)"


@dataclass(frozen=True)
class ServiceRow:
    """One row of `localstack service`."""

    name: str
    url: str
    job: str
    job_source: JobSource
    health: str
    backend: str = ""
    services: list[str] = field(default_factory=list)


def _check_state(names: list[str], checks: list[Check]) -> str:
    """The worst state across the Consul checks for these service names."""
    relevant = [check for check in checks if check.service in names]
    if not relevant:
        return NO_CHECK
    failing = [check for check in relevant if check.failing]
    if failing:
        return ", ".join(sorted({check.status for check in failing}))
    return "passing"


def join(
    routes: list[Route],
    jobs: list[Job],
    checks: list[Check],
    service_names: dict[str, list[str]] | None = None,
    *,
    catalog: dict[str, list[str]],
) -> list[ServiceRow]:
    """Every route and every job, with health where it is known.

    `service_names` maps a job id to the Consul service names that job
    registers, read off `GET /v1/job/<id>`. It is a lookup rather than a
    field on `Job` because the job list does not carry it, and because
    guessing the service name from the job id produces a confident wrong
    health column. A job absent from the map has no known service and
    therefore no known health.

    `catalog` maps every registered Consul service name to its tags, and it
    is what rung (b) resolves against. Required and keyword-only, both
    deliberately. Required because any default would be either an empty
    mapping, silently resolving nothing at rung (b), or a set derived from
    the checks, which is the defect this parameter exists to remove.
    Keyword-only because it is positionally interchangeable with
    `service_names`, so a positional form would let an unchanged caller bind
    its names dict here and type-check clean, shipping the bug green and
    degrading every `job-id` row's health to `no check`.
    """
    names_for = service_names or {}
    by_id = {job.name: job for job in jobs}
    consul_services = set(catalog)
    rows: list[ServiceRow] = []
    routed_jobs: set[str] = set()

    for route in sorted(routes, key=lambda item: item.name):
        backend = f"{route.backend_host}:{route.backend_port}"
        job = by_id.get(route.name)
        if job is not None:
            routed_jobs.add(job.name)
            names = sorted(names_for.get(job.name, []))
            rows.append(
                ServiceRow(
                    name=route.name,
                    url=route.url,
                    job=job.name,
                    job_source=JobSource.JOB_ID,
                    health=_check_state(names, checks),
                    backend=backend,
                    services=names,
                )
            )
        elif route.name in consul_services:
            rows.append(
                ServiceRow(
                    name=route.name,
                    url=route.url,
                    job=AGENT_ENDPOINT,
                    job_source=JobSource.CONSUL_NAME,
                    health=_check_state([route.name], checks),
                    backend=backend,
                    services=[route.name],
                )
            )
        else:
            rows.append(
                ServiceRow(
                    name=route.name,
                    url=route.url,
                    job=NOT_FOUND,
                    job_source=JobSource.UNRESOLVED,
                    health=NOT_FOUND,
                    backend=backend,
                )
            )

    for job in sorted(jobs, key=lambda item: item.name):
        if job.name in routed_jobs:
            continue
        names = sorted(names_for.get(job.name, []))
        rows.append(
            ServiceRow(
                name=job.name,
                url="",
                job=job.name,
                job_source=JobSource.NO_ROUTE,
                health=_check_state(names, checks),
                services=names,
            )
        )
    return rows


def find(rows: list[ServiceRow], name: str) -> tuple[ServiceRow, str] | None:
    """One row by name, and how it matched: a route name first, then a job id."""
    for row in rows:
        if row.name == name and row.job_source is not JobSource.NO_ROUTE:
            return row, "route"
    for row in rows:
        if row.job == name or row.name == name:
            return row, "job"
    return None
