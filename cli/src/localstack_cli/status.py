"""Reachability probes and the current Vault identity.

Everything here answers one question the banner asks: can this machine reach
the cluster right now, and as whom. Probes are read-only and never mint,
renew or revoke anything. D2 owns login; this only reports on a token that
already exists.
"""

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from localstack_cli.auth.vault_token_file import current_token
from localstack_cli.config import Config, ConfigError

# Long enough for a cluster on the far side of a tailnet, short enough that a
# down node does not make the banner feel broken.
TIMEOUT_SECONDS = 1.5

__all__ = ["ClusterStatus", "Identity", "Probe", "current_token", "probe_cluster"]


@dataclass(frozen=True)
class Probe:
    """One service, reachable or not, with the reason when not."""

    name: str
    address: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class Identity:
    """Who the local Vault token belongs to, when there is one."""

    logged_in: bool
    detail: str


@dataclass(frozen=True)
class ClusterStatus:
    probes: tuple[Probe, ...]
    identity: Identity


def _get(url: str, token: str | None = None) -> tuple[int, bytes]:
    """GET a URL, returning the status even when it is an error status.

    An HTTP error is still an answer: a sealed Vault replies 503 and that
    proves reachability, which a raised exception would hide.
    """
    request = urllib.request.Request(url, method="GET")
    if token:
        request.add_header("X-Vault-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


def _probe_vault(address: str) -> Probe:
    """Vault's health endpoint encodes its state in the status code."""
    try:
        status, _ = _get(f"{address}/v1/sys/health")
    except OSError as error:
        return Probe("vault", address, False, _reason(error))
    if status in (200, 429):
        return Probe("vault", address, True, "unsealed")
    if status == 503:
        return Probe("vault", address, False, "sealed")
    if status == 501:
        return Probe("vault", address, False, "not initialized")
    return Probe("vault", address, False, f"HTTP {status}")


def _probe_nomad(address: str) -> Probe:
    try:
        status, _ = _get(f"{address}/v1/agent/health")
    except OSError as error:
        return Probe("nomad", address, False, _reason(error))
    ok = status == 200
    return Probe("nomad", address, ok, "ready" if ok else f"HTTP {status}")


def _probe_consul(address: str) -> Probe:
    try:
        status, body = _get(f"{address}/v1/status/leader")
    except OSError as error:
        return Probe("consul", address, False, _reason(error))
    if status != 200:
        return Probe("consul", address, False, f"HTTP {status}")
    # A cluster mid-election answers 200 with an empty quoted string, which is
    # reachable but not usable. Say which.
    leader = body.decode(errors="replace").strip().strip('"')
    if not leader:
        return Probe("consul", address, False, "no leader")
    return Probe("consul", address, True, f"leader {leader}")


def _reason(error: OSError) -> str:
    """Collapse a socket error to something that fits on one line."""
    if isinstance(error, TimeoutError):
        return "timed out"
    message = str(getattr(error, "reason", error)) or error.__class__.__name__
    return message.removeprefix("[Errno 111] ").strip()


def probe_identity(vault_addr: str, token: str | None) -> Identity:
    if not token:
        return Identity(False, "no token; run `localstack login`")
    try:
        status, body = _get(f"{vault_addr}/v1/auth/token/lookup-self", token=token)
    except OSError as error:
        return Identity(False, f"token present, Vault unreachable ({_reason(error)})")
    if status == 403:
        return Identity(False, "token expired or revoked")
    if status != 200:
        return Identity(False, f"token lookup failed (HTTP {status})")
    try:
        data = json.loads(body)["data"]
    except (ValueError, KeyError):
        return Identity(False, "token lookup returned an unexpected body")
    return Identity(True, f"{_display_name(data)} ({_ttl(data)})")


def _display_name(data: dict[str, object]) -> str:
    """The most human of the names Vault returns for a token."""
    meta = data.get("meta")
    if isinstance(meta, dict):
        username = meta.get("username")
        if isinstance(username, str) and username:
            return username
    name = data.get("display_name")
    return name if isinstance(name, str) and name else "unknown"


def _ttl(data: dict[str, object]) -> str:
    ttl = data.get("ttl")
    if not isinstance(ttl, int):
        return "ttl unknown"
    if ttl == 0:
        # Vault reports 0 for a token that never expires, which for a human
        # session is worth seeing rather than reading as "expired".
        return "does not expire"
    hours, seconds = divmod(ttl, 3600)
    minutes = seconds // 60
    return f"{hours}h{minutes:02d}m left" if hours else f"{minutes}m left"


def probe_cluster() -> ClusterStatus:
    """Probe all three services at once, plus the local token.

    Sequentially this costs three timeouts when the cluster is unreachable,
    which is exactly when someone is staring at the banner waiting.
    """
    try:
        config = Config.from_env()
    except ConfigError as error:
        return ClusterStatus((), Identity(False, str(error)))

    checks = (
        (_probe_vault, config.vault_addr),
        (_probe_nomad, config.nomad_addr),
        (_probe_consul, config.consul_addr),
    )
    token = current_token()
    with ThreadPoolExecutor(max_workers=4) as pool:
        identity = pool.submit(probe_identity, config.vault_addr, token)
        probes = tuple(pool.map(lambda c: c[0](c[1]), checks))
    return ClusterStatus(probes, identity.result())
