"""Nomad reads: job statuses, nodes, and one job's service names.

Copied down from `cli/src/localstack_cli/api/nomad.py` (Requirement 3, this
app's backend must not depend on `cli` at all). Narrowed to what `status.py`
and `live.py` actually use: `job_templates`/`Template` are dropped, since
this app never reads a job's raw template text.
"""

from dataclasses import dataclass, field
from typing import Any

from dash_app._http import TIMEOUT_SECONDS, get_json

TOKEN_HEADER = "X-Nomad-Token"

# Nomad pages `/v1/jobs/statuses` and signals more with this header. Send no
# per_page and follow it while non-empty, or the panel silently under-reports
# the day this cluster outgrows one page.
NEXT_TOKEN_HEADER = "X-Nomad-Nexttoken"

# A page is never followed more times than this. A server that always returns
# a next-token would otherwise spin forever inside a refresh.
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
        body, headers = get_json(url, token=token, token_header=TOKEN_HEADER, timeout=timeout)
        jobs.extend(_parse_job(item) for item in body if isinstance(item, dict))

        next_token = headers.get(NEXT_TOKEN_HEADER, "")
        if not next_token:
            break

    return jobs


def list_nodes(address: str, token: str | None, timeout: float = TIMEOUT_SECONDS) -> list[Node]:
    """Every client node, in one call."""
    url = f"{address.rstrip('/')}/v1/nodes"
    body, _ = get_json(url, token=token, token_header=TOKEN_HEADER, timeout=timeout)
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


def get_job(address: str, token: str | None, job_id: str, timeout: float = TIMEOUT_SECONDS) -> Any:
    """One job's full specification."""
    url = f"{address.rstrip('/')}/v1/job/{job_id}"
    body, _ = get_json(url, token=token, token_header=TOKEN_HEADER, timeout=timeout)
    return body


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
