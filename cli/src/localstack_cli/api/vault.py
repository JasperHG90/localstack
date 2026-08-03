"""Vault seal state.

`GET /v1/sys/seal-status` needs no token, verified against this cluster. That
makes it the one panel that still renders when the session is dead, which
matters because a sealed Vault after a reboot is the common real outage here
and the root `justfile` carries `unseal_vault` for exactly that.
"""

from dataclasses import dataclass

from localstack_cli.api._http import TIMEOUT_SECONDS, get_json
from localstack_cli.api.errors import MissingCapability, NotAuthenticated, NotFound

SERVICE = "vault"
# Named for the 403 message even though this read needs no grant, so a
# tightened listener still degrades to a sentence rather than a blank panel.
SEAL_READ = "sys/seal-status read"
VAULT_TOKEN_HEADER = "X-Vault-Token"


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


# Named for the message a 403 produces. `default` grants neither of these;
# the `developer` policy does.
POLICY_READ = "sys/policies/acl/* read"
METADATA_READ = "secret/metadata/* read"


@dataclass(frozen=True)
class Health:
    """What `sys/health` says. No token needed, so it always answers."""

    initialized: bool
    sealed: bool
    standby: bool
    version: str


def health(address: str, timeout: float = TIMEOUT_SECONDS) -> Health:
    """Vault's own health. The one read that works with a dead session."""
    url = f"{address.rstrip('/')}/v1/sys/health"
    body, _ = get_json(SERVICE, url, SEAL_READ, timeout=timeout)
    return Health(
        initialized=bool(body.get("initialized", False)),
        sealed=bool(body.get("sealed", False)),
        standby=bool(body.get("standby", False)),
        version=str(body.get("version", "")),
    )


def token_is_live(address: str, token: str, timeout: float = TIMEOUT_SECONDS) -> bool:
    """Whether the session's own token still resolves.

    This is what separates "not logged in" from "not allowed". A 403 on a
    real call plus a 200 here means the token is fine and the policy is not,
    so telling the developer to log in again would send them in a circle.
    """
    url = f"{address.rstrip('/')}/v1/auth/token/lookup-self"
    try:
        get_json(
            SERVICE,
            url,
            "token lookup",
            token=token,
            token_header=VAULT_TOKEN_HEADER,
            timeout=timeout,
        )
    except (NotAuthenticated, MissingCapability):
        return False
    return True


def read_policy(address: str, token: str, name: str, timeout: float = TIMEOUT_SECONDS) -> str:
    """A policy's text, fetched at runtime and never embedded in the source."""
    url = f"{address.rstrip('/')}/v1/sys/policies/acl/{name}"
    body, _ = get_json(
        SERVICE, url, POLICY_READ, token=token, token_header=VAULT_TOKEN_HEADER, timeout=timeout
    )
    return str(body.get("data", {}).get("policy", ""))


def metadata_exists(address: str, token: str, path: str, timeout: float = TIMEOUT_SECONDS) -> str:
    """Whether a KV2 path is there: `present`, `missing` or `denied`.

    Metadata, never the read prefix. The metadata endpoint carries versions
    and timestamps and no `data` field, so the value cannot be read even by
    accident.

    `denied` is a third state and is never folded into `missing`. Telling a
    developer their secret does not exist when they merely cannot see it is
    the worse error: it sends them to write one that is already there.
    """
    url = f"{address.rstrip('/')}/v1/{path}"
    try:
        get_json(
            SERVICE,
            url,
            METADATA_READ,
            token=token,
            token_header=VAULT_TOKEN_HEADER,
            timeout=timeout,
        )
    except NotFound:
        return "missing"
    except (MissingCapability, NotAuthenticated):
        return "denied"
    return "present"
