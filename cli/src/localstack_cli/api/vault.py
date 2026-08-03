"""Vault seal state.

`GET /v1/sys/seal-status` needs no token, verified against this cluster. That
makes it the one panel that still renders when the session is dead, which
matters because a sealed Vault after a reboot is the common real outage here
and the root `justfile` carries `unseal_vault` for exactly that.
"""

from dataclasses import dataclass

from localstack_cli.api._http import TIMEOUT_SECONDS, get_json

SERVICE = "vault"
# Named for the 403 message even though this read needs no grant, so a
# tightened listener still degrades to a sentence rather than a blank panel.
SEAL_READ = "sys/seal-status read"


@dataclass(frozen=True)
class SealStatus:
    """Whether Vault is sealed, and how far an unseal has got."""

    sealed: bool
    threshold: int
    shares: int
    progress: int
    version: str

    @property
    def summary(self) -> str:
        if not self.sealed:
            return "unsealed"
        return f"SEALED  {self.progress}/{self.threshold} keys entered"


def seal_status(address: str, timeout: float = TIMEOUT_SECONDS) -> SealStatus:
    """Read the seal state. No token is sent, because none is needed."""
    url = f"{address.rstrip('/')}/v1/sys/seal-status"
    body, _ = get_json(SERVICE, url, SEAL_READ, timeout=timeout)
    return SealStatus(
        sealed=bool(body.get("sealed", False)),
        threshold=int(body.get("t") or 0),
        shares=int(body.get("n") or 0),
        progress=int(body.get("progress") or 0),
        version=str(body.get("version", "")),
    )
