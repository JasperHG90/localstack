"""Join the tile's synthetic routes, Nomad's jobs and Consul's checks.

Copied down from `cli/src/localstack_cli/api/services.py` (Requirement 3,
this app's backend must not depend on `cli` at all). `find()` is dropped:
dash never looks a single row up by name, it renders the whole set. The
`Route` dataclass is copied separately from
`cli/src/localstack_cli/api/haproxy.py:46-57` -- dash only ever builds
synthetic routes (`status.build_routes`), never parses a live haproxy
config, so none of that module's parsing logic or its `HaproxyParseError`
comes with it.
"""

from dataclasses import dataclass, field
from enum import Enum

from dash_app.consul_client import Check
from dash_app.nomad_client import Job


@dataclass(frozen=True)
class Route:
    """One hostname the edge serves, and where it sends it."""

    name: str
    hostname: str
    backend_host: str
    backend_port: int

    @property
    def url(self) -> str:
        return f"https://{self.hostname}"


class JobSource(Enum):
    """Which rung of the ladder resolved a row."""

    JOB_ID = "job-id"
    CONSUL_NAME = "consul-name"
    # Matched on a tag rather than a name, and only when exactly one service
    # carries it. Distinct from CONSUL_NAME because the name did not match.
    CONSUL_TAG = "consul-tag"
    UNRESOLVED = "unresolved"
    # A job with no route at all.
    NO_ROUTE = "no-route"


# What the health column says when there is nothing to say. Not "healthy":
# absence of a check is not evidence of health.
NO_CHECK = "no check"
NOT_FOUND = "not found"
AGENT_ENDPOINT = "no job (agent endpoint)"


@dataclass(frozen=True)
class ServiceRow:
    """One route/job, joined against Consul's checks."""

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


def _sole_tag_carrier(name: str, catalog: dict[str, list[str]]) -> str | None:
    """The one service carrying `name` as a tag, or `None`.

    `None` for zero carriers and for two or more. Resolving on two would mean
    picking whichever sorts first, which is the guess this rung exists to
    avoid.
    """
    carriers = [service for service, tags in catalog.items() if name in tags]
    return carriers[0] if len(carriers) == 1 else None


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

    `catalog` maps every registered Consul service name to its tags. Rung
    (b) resolves against its keys and the tag rung against its values.
    Required and keyword-only, both deliberately. Required because any
    default would be either an empty mapping, silently resolving nothing at
    rung (b), or a set derived from the checks, which is the defect this
    parameter exists to remove. Keyword-only because it is positionally
    interchangeable with `service_names`, so a positional form would let an
    unchanged caller bind its names dict here and type-check clean, shipping
    the bug green and degrading every `job-id` row's health to `no check`.
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
        elif (tagged := _sole_tag_carrier(route.name, catalog)) is not None:
            # The job named the tag itself. The matched service goes in the
            # job column, and the rung does NOT mark it routed: a tag can be
            # the only thing pointing at a job, and suppressing that job's
            # own row would lose it.
            rows.append(
                ServiceRow(
                    name=route.name,
                    url=route.url,
                    job=tagged,
                    job_source=JobSource.CONSUL_TAG,
                    health=_check_state([tagged], checks),
                    backend=backend,
                    services=[tagged],
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
