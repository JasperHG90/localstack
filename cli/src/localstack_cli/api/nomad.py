"""Nomad reads: job statuses and nodes.

The job source is `GET /v1/jobs/statuses`, never `GET /v1/jobs`. Two reasons,
both measured against this cluster.

`/v1/jobs` carries `JobSummary.Summary.<group>.{Failed,Lost,Complete}`, which
are cumulative LIFETIME allocation counters, not current state. Eight of the
fourteen healthy service jobs here carry `Failed > 0` while running at their
full desired count. A panel built on them reds most of the cluster on a good
day, and a panel that cries wolf is worse than no panel.

`/v1/jobs` also carries no desired count at all, so building the job widget on
it needs a per-job read: fifteen extra calls every refresh instead of one.

`/v1/jobs/statuses` elements carry no `JobSummary` key at all, which is the
strongest guarantee those counters can never reach the panel.
"""

from dataclasses import dataclass, field
from typing import Any

from localstack_cli.api._http import TIMEOUT_SECONDS, get_json

SERVICE = "nomad"
TOKEN_HEADER = "X-Nomad-Token"

# The grant each call needs, named so a 403 can say which one is missing.
LIST_JOBS = "list-jobs"
NODE_READ = "node:read"
READ_JOB = "read-job"

# Nomad pages `/v1/jobs/statuses` and signals more with this header. Send no
# per_page and follow it while non-empty, or the panel silently under-reports
# the day this cluster outgrows one page.
NEXT_TOKEN_HEADER = "X-Nomad-Nexttoken"

# A page is never followed more times than this. A server that always returns
# a next-token would otherwise spin forever inside a 2-second refresh.
MAX_PAGES = 50


@dataclass(frozen=True)
class Alloc:
    """One current allocation of a job."""

    client_status: str
    group: str
    node_id: str

    @property
    def running(self) -> bool:
        return self.client_status == "running"


@dataclass(frozen=True)
class Job:
    """One job's current state, as `/v1/jobs/statuses` reports it."""

    name: str
    job_type: str
    status: str
    stopped: bool
    desired: int
    allocs: list[Alloc] = field(default_factory=list)
    # `null` on service and system jobs, a list on a periodic parent. That
    # distinction is how a parent is spotted, so the raw None is kept.
    child_statuses: list[str] | None = None

    @property
    def is_periodic_parent(self) -> bool:
        return self.child_statuses is not None

    @property
    def running_allocs(self) -> int:
        return sum(1 for alloc in self.allocs if alloc.running)


@dataclass(frozen=True)
class Node:
    """One Nomad client node."""

    name: str
    status: str
    eligibility: str
    draining: bool

    @property
    def usable(self) -> bool:
        return self.status == "ready" and self.eligibility == "eligible" and not self.draining


def _parse_job(raw: dict[str, Any]) -> Job:
    # `Allocs` comes back as JSON null on a periodic parent, not an empty
    # list, so every downstream `len()` would raise without this.
    raw_allocs = raw.get("Allocs") or []
    allocs = [
        Alloc(
            client_status=str(item.get("ClientStatus", "")),
            group=str(item.get("Group", "")),
            node_id=str(item.get("NodeID", "")),
        )
        for item in raw_allocs
        if isinstance(item, dict)
    ]
    children = raw.get("ChildStatuses")
    return Job(
        name=str(raw.get("Name", "")),
        job_type=str(raw.get("Type", "")),
        status=str(raw.get("Status", "")),
        stopped=bool(raw.get("Stop", False)),
        desired=int(raw.get("GroupCountSum") or 0),
        allocs=allocs,
        child_statuses=[str(child) for child in children] if isinstance(children, list) else None,
    )


def job_statuses(address: str, token: str | None, timeout: float = TIMEOUT_SECONDS) -> list[Job]:
    """Every job's current state, following pagination."""
    jobs: list[Job] = []
    next_token = ""

    for _ in range(MAX_PAGES):
        url = f"{address.rstrip('/')}/v1/jobs/statuses"
        if next_token:
            url = f"{url}?next_token={next_token}"
        body, headers = get_json(
            SERVICE, url, LIST_JOBS, token=token, token_header=TOKEN_HEADER, timeout=timeout
        )
        jobs.extend(_parse_job(item) for item in body if isinstance(item, dict))

        next_token = headers.get(NEXT_TOKEN_HEADER, "")
        if not next_token:
            break

    return jobs


def list_nodes(address: str, token: str | None, timeout: float = TIMEOUT_SECONDS) -> list[Node]:
    """Every client node, in one call."""
    url = f"{address.rstrip('/')}/v1/nodes"
    body, _ = get_json(
        SERVICE, url, NODE_READ, token=token, token_header=TOKEN_HEADER, timeout=timeout
    )
    return [
        Node(
            name=str(item.get("Name", "")),
            status=str(item.get("Status", "")),
            eligibility=str(item.get("SchedulingEligibility", "")),
            draining=bool(item.get("Drain", False)),
        )
        for item in body
        if isinstance(item, dict)
    ]


@dataclass(frozen=True)
class Template:
    """One rendered template a job task carries.

    `text` is the template body, and it is handled carefully: the running
    haproxy job's body holds a live basic-auth password. Callers extract what
    they need and never store or print the body itself.
    """

    task: str
    dest_path: str
    text: str


def get_job(address: str, token: str | None, job_id: str, timeout: float = TIMEOUT_SECONDS) -> Any:
    """One job's full specification."""
    url = f"{address.rstrip('/')}/v1/job/{job_id}"
    body, _ = get_json(
        SERVICE, url, READ_JOB, token=token, token_header=TOKEN_HEADER, timeout=timeout
    )
    return body


def job_templates(
    address: str, token: str | None, job_id: str, timeout: float = TIMEOUT_SECONDS
) -> list[Template]:
    """Every template block in a job, as `(task, dest_path, text)`.

    The single door to `EmbeddedTmpl`. Nothing else may reach for it, so
    there is one place to audit when asking whether template text can escape.
    """
    spec = get_job(address, token, job_id, timeout=timeout)
    found = []
    for group in spec.get("TaskGroups") or []:
        for task in group.get("Tasks") or []:
            for template in task.get("Templates") or []:
                found.append(
                    Template(
                        task=str(task.get("Name", "")),
                        dest_path=str(template.get("DestPath", "")),
                        text=str(template.get("EmbeddedTmpl") or ""),
                    )
                )
    return found


def job_service_names(
    address: str, token: str | None, job_id: str, timeout: float = TIMEOUT_SECONDS
) -> list[str]:
    """The Consul service names a job registers.

    Read off the job rather than guessed from its id. A job whose service is
    named differently would otherwise get a confident, wrong health column.
    """
    spec = get_job(address, token, job_id, timeout=timeout)
    names = []
    for group in spec.get("TaskGroups") or []:
        for service in group.get("Services") or []:
            names.append(str(service.get("Name", "")))
        for task in group.get("Tasks") or []:
            for service in task.get("Services") or []:
                names.append(str(service.get("Name", "")))
    return sorted({name for name in names if name})
