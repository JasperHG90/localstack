"""One view of all three systems, fetched at once.

The reason this is one command rather than three is that it fetches Vault,
Nomad and Consul concurrently and shows all three answers together. That only
pays off if a failure in one cannot touch the others, so each section is
either data or a named error, and no exception from one fetch escapes to kill
another.

Three green panels produced by a swallowed timeout is the failure this
exists to prevent, so a run with any failed section exits non-zero.

Vault's `sys/health` needs no token, which makes it the section that answers
even when the session is dead.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from localstack_cli.api import consul, nomad, vault
from localstack_cli.api._http import TIMEOUT_SECONDS
from localstack_cli.api.errors import ClusterError

T = TypeVar("T")


@dataclass(frozen=True)
class Section(Generic[T]):
    """One system's answer: data, or the reason there is none."""

    name: str
    value: T | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class ClusterStatus:
    """What every section said."""

    vault: Section[vault.Health]
    nodes: Section[list[nomad.Node]]
    jobs: Section[list[nomad.Job]]
    checks: Section[list[consul.Check]]

    @property
    def sections(self) -> list[Section[Any]]:
        return [self.vault, self.nodes, self.jobs, self.checks]

    @property
    def ok(self) -> bool:
        return all(section.ok for section in self.sections)

    @property
    def failed(self) -> list[str]:
        return [section.name for section in self.sections if not section.ok]


def _run(name: str, fetch: Any) -> Section[Any]:
    """One fetch, with its failure captured rather than raised.

    Every exception is caught, not just `ClusterError`. An unclassified error
    in one source killing the other three is exactly the coupling this module
    exists to remove.
    """
    try:
        return Section(name=name, value=fetch())
    except ClusterError as error:
        return Section(name=name, error=str(error))
    except Exception as error:  # noqa: BLE001
        return Section(name=name, error=f"{type(error).__name__}: {error}")


def fetch(
    vault_addr: str,
    nomad_addr: str,
    consul_addr: str,
    nomad_token: str | None,
    timeout: float = TIMEOUT_SECONDS,
) -> ClusterStatus:
    """All four reads at once, each with its own timeout."""
    calls = [
        ("vault", lambda: vault.health(vault_addr, timeout=timeout)),
        ("nodes", lambda: nomad.list_nodes(nomad_addr, nomad_token, timeout=timeout)),
        ("jobs", lambda: nomad.job_statuses(nomad_addr, nomad_token, timeout=timeout)),
        ("consul", lambda: consul.list_checks(consul_addr, timeout=timeout)),
    ]
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        results = list(pool.map(lambda call: _run(*call), calls))
    return ClusterStatus(vault=results[0], nodes=results[1], jobs=results[2], checks=results[3])
