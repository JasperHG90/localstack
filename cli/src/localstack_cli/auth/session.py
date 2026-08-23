"""The credential cache: one file holding the Vault session and what it brokered.

One file, four entries, because their lifetimes differ. The Vault token lives
for days; the brokered Nomad (`deploy` and `manage`) and Consul leases cap at
an hour. `expires_at` is absolute, computed from each response's
`lease_duration` at receipt, so a clock read decides freshness rather than a
countdown nobody is running.

Nothing here talks to the network. Every function takes the path, so tests
point it at a temp directory instead of the developer's real config.
"""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

# A credential inside this window is treated as already gone. Re-brokering
# costs one request; handing out a token that dies mid-`terraform apply`
# costs an afternoon.
DEFAULT_SKEW = timedelta(minutes=5)

DIRECTORY_MODE = 0o700


class SessionError(RuntimeError):
    """The cache exists but cannot be used."""


@dataclass(frozen=True)
class Credential:
    """One credential and when it dies.

    `lease_id` is empty for the Vault token, which is not a lease. `entity_id`
    and `policies` are the Vault token's alone; the brokered pair carry
    neither.
    """

    token: str
    accessor: str
    expires_at: datetime
    renewable: bool
    lease_id: str = ""
    entity_id: str = ""
    policies: tuple[str, ...] = ()

    def is_stale(self, now: datetime | None = None, skew: timedelta = DEFAULT_SKEW) -> bool:
        moment = now if now is not None else datetime.now(UTC)
        return self.expires_at - skew <= moment

    def seconds_left(self, now: datetime | None = None) -> int:
        moment = now if now is not None else datetime.now(UTC)
        return max(0, int((self.expires_at - moment).total_seconds()))


@dataclass(frozen=True)
class Session:
    """A login and the credentials brokered from it."""

    method: str
    vault_addr: str
    username: str
    vault: Credential
    nomad: Credential | None = None
    nomad_manage: Credential | None = None
    consul: Credential | None = None
    version: int = SCHEMA_VERSION

    def credential(self, service: str) -> Credential | None:
        """The credential for a service name, or None when not brokered."""
        return {
            "vault": self.vault,
            "nomad": self.nomad,
            "nomad_manage": self.nomad_manage,
            "consul": self.consul,
        }.get(service)


def session_path() -> Path:
    """Where the cache lives.

    Under `XDG_CONFIG_HOME` when set, so tests and containers can move it.
    Never inside the repo: loop worktrees live under `.loop/worktrees/` and a
    stray token there would not be gitignored.
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "localstack" / "session.json"


def _encode(value: Credential | None) -> dict[str, Any] | None:
    if value is None:
        return None
    data = asdict(value)
    data["expires_at"] = value.expires_at.isoformat()
    data["policies"] = list(value.policies)
    return data


def _decode(data: Any, name: str) -> Credential | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise SessionError(f"session file: `{name}` is not an object")
    try:
        expires_at = datetime.fromisoformat(str(data["expires_at"]))
        return Credential(
            token=str(data["token"]),
            accessor=str(data["accessor"]),
            expires_at=expires_at,
            renewable=bool(data["renewable"]),
            lease_id=str(data.get("lease_id", "")),
            entity_id=str(data.get("entity_id", "")),
            policies=tuple(str(policy) for policy in data.get("policies", ())),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SessionError(f"session file: `{name}` is malformed ({error})") from error


def save(session: Session, path: Path) -> None:
    """Write the cache so it is never briefly readable by anyone else.

    The mode is set when the file is CREATED, not chmod-ed afterwards: a
    chmod leaves a window in which the token is world-readable. The temp file
    shares the destination's directory so the rename cannot cross a
    filesystem and degrade into a copy.
    """
    path.parent.mkdir(parents=True, mode=DIRECTORY_MODE, exist_ok=True)
    # mkdir's mode is subject to umask, and an existing directory keeps its
    # own. Say what we mean either way.
    path.parent.chmod(DIRECTORY_MODE)

    body = json.dumps(
        {
            "version": session.version,
            "method": session.method,
            "vault_addr": session.vault_addr,
            "username": session.username,
            "vault": _encode(session.vault),
            "nomad": _encode(session.nomad),
            "nomad_manage": _encode(session.nomad_manage),
            "consul": _encode(session.consul),
        },
        indent=2,
    )

    # `mkstemp` picks a name nothing else holds and creates it 0600 with
    # O_EXCL, which is both properties this needs. A hand-rolled
    # ".<name>.<pid>" collides: a temp file left by a SIGKILLed run blocks
    # every later write once that pid is recycled.
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(body + "\n")
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def load(path: Path) -> Session | None:
    """Read the cache. None when there is no session, an error when it is broken.

    A missing file is an ordinary state: nobody has logged in. A file that
    exists but does not parse is not, and saying which is which is the
    difference between "run `localstack login`" and an unexplained traceback.
    """
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SessionError(f"cannot read {path}: {error}") from error

    try:
        data = json.loads(raw)
    except ValueError as error:
        raise SessionError(f"session file at {path} is not valid JSON ({error})") from error
    if not isinstance(data, dict):
        raise SessionError(f"session file at {path} is not an object")

    version = data.get("version")
    if version != SCHEMA_VERSION:
        raise SessionError(
            f"session file at {path} has version {version!r}, expected {SCHEMA_VERSION}. "
            "Run `localstack logout` and log in again."
        )

    vault = _decode(data.get("vault"), "vault")
    if vault is None:
        raise SessionError(f"session file at {path} has no vault credential")

    return Session(
        method=str(data.get("method", "userpass")),
        vault_addr=str(data.get("vault_addr", "")),
        username=str(data.get("username", "")),
        vault=vault,
        nomad=_decode(data.get("nomad"), "nomad"),
        nomad_manage=_decode(data.get("nomad_manage"), "nomad_manage"),
        consul=_decode(data.get("consul"), "consul"),
        version=SCHEMA_VERSION,
    )


def delete(path: Path) -> bool:
    """Remove the cache. True when there was one to remove."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def expires_at(lease_duration: int, now: datetime | None = None) -> datetime:
    """Turn a response's `lease_duration` into an absolute moment."""
    moment = now if now is not None else datetime.now(UTC)
    return moment + timedelta(seconds=lease_duration)
