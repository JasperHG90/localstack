"""What can go wrong reading a cluster, as states rather than tracebacks.

Every fetcher maps its failures onto these, so a caller never sees an
`httpx` type. Each carries the service name, because a panel that says
"unreachable" without naming what is unreachable sends someone to check the
wrong thing.

The distinction that matters most is `NotAuthenticated` against
`MissingCapability`. An expired token means run `localstack login`; a missing
capability means the policy does not grant the read. Conflating them sends a
developer to re-login over a policy gap, or to debug a policy over a lapsed
token.
"""


class ClusterError(RuntimeError):
    """A read failed. Every subclass names the service it failed against."""

    def __init__(self, service: str, detail: str = "") -> None:
        self.service = service
        self.detail = detail
        super().__init__(self.message())

    def message(self) -> str:
        return f"{self.service}: {self.detail}" if self.detail else self.service


class NotAuthenticated(ClusterError):
    """The token is absent, expired or revoked. The fix is a fresh login."""

    def message(self) -> str:
        return f"{self.service}: not authenticated. Run `localstack login`."


class MissingCapability(ClusterError):
    """The token authenticates but the policy does not grant this read."""

    def __init__(self, service: str, capability: str) -> None:
        self.capability = capability
        super().__init__(service, capability)

    def message(self) -> str:
        return f"{self.service}: denied. The token lacks {self.capability}."


class NotFound(ClusterError):
    """The endpoint answered, but the thing asked for is not there."""


class Unreachable(ClusterError):
    """Nothing answered at the address."""

    def message(self) -> str:
        return f"{self.service}: unreachable at {self.detail}"


class Timeout(ClusterError):
    """Something answered too slowly to wait for."""

    def message(self) -> str:
        return f"{self.service}: timed out after {self.detail}"
