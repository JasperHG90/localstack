"""Consul health checks.

`GET /v1/health/state/any` answers 200 with no token here, and that is a
config side effect rather than a grant: the agent's `tokens.default` is set
to the agent token, so a tokenless HTTP call authenticates as the agent even
though `default_policy = "deny"`. Three probes pin the mechanism down. The
tokenless read is 200, the same read with a bogus token is 403, and a
tokenless `GET /v1/acl/tokens` is 403.

So no Consul token is brokered for it: asking for a credential a read does
not need is unearned work. If that config ever tightens, this degrades to
"denied" like any other source, which is the designed behavior rather than a
crash.

Every check is returned and the widget filters. A Nomad allocation can be
`running` while its Consul check is critical, and that gap is the only reason
this panel exists.
"""

from dataclasses import dataclass

from localstack_cli.api._http import TIMEOUT_SECONDS, get_json

SERVICE = "consul"
HEALTH_READ = "service:read"

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
    body, _ = get_json(SERVICE, url, HEALTH_READ, timeout=timeout)
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


def failing(checks: list[Check]) -> list[Check]:
    """The checks worth showing. Never the wall of passing ones."""
    return [check for check in checks if check.failing]


def list_services(address: str, timeout: float = TIMEOUT_SECONDS) -> dict[str, list[str]]:
    """Every registered service, mapped to its tags. No token is sent.

    This is what answers "does Consul know about a service by this name",
    and it is not the same question as "does Consul health-check it".
    Consul registers itself in the catalog, but its only check is a
    node-level `serfHealth` with an empty `ServiceName`, so a name set built
    from checks silently omits `consul`.

    The tags come back rather than being dropped. `minio` carries `s3`,
    declared by the job on the port label the `s3` route points at, so a
    later rung could resolve that route from data rather than a guess. A
    `list[str]` return would foreclose it.
    """
    url = f"{address.rstrip('/')}/v1/catalog/services"
    body, _ = get_json(SERVICE, url, HEALTH_READ, timeout=timeout)
    return {
        str(name): [str(tag) for tag in (tags or [])]
        for name, tags in body.items()
        if isinstance(tags, list)
    }
