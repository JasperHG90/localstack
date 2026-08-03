"""The four panels. Each takes a result and renders it. No I/O here.

Every widget renders one of three things: data, a named problem, or the last
data it had marked stale. Degraded states are the point of this panel, not
error handling bolted on: a developer opens it exactly when something is
wrong, and "sealed" or "no token" is the answer they came for.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from textual.widgets import Static

from localstack_cli.api.consul import Check, failing
from localstack_cli.api.health import Health, JobHealth
from localstack_cli.api.nomad import Node
from localstack_cli.api.vault import SealStatus

T = TypeVar("T")

# Shown before the first fetch lands. Distinct from an empty table, which
# would read as "nothing is running" rather than "nothing is known yet".
NO_DATA = "no data yet"

MARKS = {
    Health.HEALTHY: "ok",
    Health.DEGRADED: "DEGRADED",
    Health.STOPPED: "stopped",
    Health.UNKNOWN: "unknown",
}


@dataclass(frozen=True)
class Result(Generic[T]):
    """What one source last produced.

    `problem` set with `value` still present is the stale case: the fetch
    failed but a previous one succeeded, so the panel keeps the old value and
    says it is old. Blanking instead would throw away the only information on
    screen at the moment it is wanted.
    """

    value: T | None = None
    problem: str | None = None

    @property
    def stale(self) -> bool:
        return self.problem is not None and self.value is not None

    @property
    def empty(self) -> bool:
        return self.value is None


class Panel(Static):
    """A titled block of text, rendered from a `Result`."""

    title = "panel"

    def show(self, result: Result[object]) -> None:
        self.update(self.render_result(result))

    def render_result(self, result: Result[object]) -> str:
        head = f"{self.title}"
        if result.empty:
            return f"{head}\n  {result.problem or NO_DATA}"
        # A successful fetch that found nothing still has something to say. A
        # blank panel reads as broken rather than as empty.
        body = self.render_value(result.value) or "  none"
        if result.stale:
            return f"{head}  (stale: {result.problem})\n{body}"
        return f"{head}\n{body}"

    def render_value(self, value: object) -> str:
        raise NotImplementedError


class VaultPanel(Panel):
    """Seal state. The only source readable without a token."""

    title = "Vault"

    def render_value(self, value: object) -> str:
        assert isinstance(value, SealStatus)
        return f"  {value.summary}"


class NodePanel(Panel):
    """One row per node. A job that will not place is often a node that left."""

    title = "Nodes"

    def render_value(self, value: object) -> str:
        assert isinstance(value, list)
        rows = []
        for node in value:
            assert isinstance(node, Node)
            mark = "ok" if node.usable else "CHECK"
            detail = f"{node.status}/{node.eligibility}"
            if node.draining:
                detail += "/draining"
            rows.append(f"  {mark:<9}{node.name:<20}{detail}")
        return "\n".join(rows)


class JobPanel(Panel):
    """One row per job, degraded first. The reason the panel exists."""

    title = "Jobs"

    def render_value(self, value: object) -> str:
        assert isinstance(value, list)
        rows = []
        for job in value:
            assert isinstance(job, JobHealth)
            if job.health is Health.UNKNOWN:
                # The node count is what is missing, so showing "5/0" would
                # claim a desired count of zero rather than an unknown one.
                counts = f"{job.running}/?"
            elif job.health is Health.HEALTHY and job.expected == 0:
                # A periodic parent has no allocations while healthy, so a
                # count says nothing about it.
                counts = ""
            else:
                counts = job.counts
            rows.append(f"  {MARKS[job.health]:<9}{job.name:<20}{job.job_type:<9}{counts}")
        return "\n".join(rows)


class ConsulPanel(Panel):
    """The failing checks, and only those. Never the wall of passing ones."""

    title = "Consul checks"

    def render_value(self, value: object) -> str:
        assert isinstance(value, list)
        checks: list[Check] = [check for check in value if isinstance(check, Check)]
        bad = failing(checks)
        head = f"  {len(bad)} failing of {len(checks)}"
        if not bad:
            return head
        rows = [f"  {check.status:<9}{check.node:<20}{check.name}" for check in bad]
        return "\n".join([head, *rows])
