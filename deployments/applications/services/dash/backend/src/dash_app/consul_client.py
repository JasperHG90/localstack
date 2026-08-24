"""Consul health checks and service catalog reads.

Copied down from `cli/src/localstack_cli/api/consul.py` (Requirement 3, this
app's backend must not depend on `cli` at all). The module-level `failing()`
helper is dropped: dash never filters a check list down to the failing ones,
it renders every tile's own worst state. `Check.failing` (the property, used
inside the copied `_check_state` in `services.py`) stays.
"""

from dataclasses import dataclass

from dash_app._http import TIMEOUT_SECONDS, get_json

PASSING = "passing"


@dataclass(frozen=True)
class Check:
    """One health check on one node."""

    name: str
    status: str
    node: str
    service: str

    @property
    def failing(self) -> bool:
        return self.status != PASSING


def list_checks(address: str, timeout: float = TIMEOUT_SECONDS) -> list[Check]:
    """Every check, passing or not. No token is sent."""
    url = f"{address.rstrip('/')}/v1/health/state/any"
    body, _ = get_json(url, timeout=timeout)
    return [
        Check(
            name=str(item.get("Name", "")),
            status=str(item.get("Status", "")),
            node=str(item.get("Node", "")),
            service=str(item.get("ServiceName", "")),
        )
        for item in body
        if isinstance(item, dict)
    ]


def list_services(address: str, timeout: float = TIMEOUT_SECONDS) -> dict[str, list[str]]:
    """Every registered service, mapped to its tags. No token is sent.

    This is what answers "does Consul know about a service by this name",
    and it is not the same question as "does Consul health-check it".
    Consul registers itself in the catalog, but its only check is a
    node-level `serfHealth` with an empty `ServiceName`, so a name set built
    from checks silently omits `consul`.
    """
    url = f"{address.rstrip('/')}/v1/catalog/services"
    body, _ = get_json(url, timeout=timeout)
    return {
        str(name): [str(tag) for tag in (tags or [])]
        for name, tags in body.items()
        if isinstance(tags, list)
    }
