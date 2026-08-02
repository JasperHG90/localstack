"""The Vault calls this CLI makes, and the refusal to send a password in clear.

Five endpoints, over `urllib`. D1 chose the stdlib and a real HTTP server in
the tests rather than a client library and a mocking layer, and five small
calls do not earn a second HTTP stack.
"""

import json
import urllib.error
import urllib.request
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

TIMEOUT_SECONDS = 10.0

# haproxy terminates TLS for the cluster. Named in the refusal below so the
# developer is told where to go, not merely that they cannot go here.
EDGE_VAULT_ADDR = "https://vault.lab.orangecluster.nl"


class VaultError(RuntimeError):
    """A Vault call failed, with a message naming what and why."""


class InsecureAddressError(VaultError):
    """The address would put a password on the wire in the clear."""


def is_plaintext_to_the_network(addr: str) -> bool:
    """True when sending a password here would cross a network unencrypted.

    Loopback over `http://` is fine: nothing leaves the host. Anything else
    over `http://` is not. The cluster's Vault listener sets
    `tls_disable: true`, so this is the live case, not a hypothetical.
    """
    parsed = urlparse(addr)
    if parsed.scheme != "http":
        return False
    host = parsed.hostname or ""
    if host in ("localhost", "localhost.localdomain"):
        return False
    try:
        return not ip_address(host).is_loopback
    except ValueError:
        # A hostname that is not an IP literal and not localhost. Assume it
        # resolves off-box, which is the safe direction to be wrong in.
        return True


def guard_address(addr: str, insecure: bool) -> str | None:
    """Return a warning to print, or raise when the address must be refused.

    Returns the warning text for `--insecure` so the caller decides where it
    goes; it belongs on stderr, and this module does not own stdout.
    """
    if not is_plaintext_to_the_network(addr):
        return None
    if not insecure:
        raise InsecureAddressError(
            f"refusing to send a password to {addr} in the clear.\n"
            f"Use the TLS edge: --vault-addr {EDGE_VAULT_ADDR}\n"
            "Or pass --insecure if you really mean to."
        )
    return f"WARNING: sending a password to {addr} unencrypted (--insecure)."


def _request(
    addr: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{addr.rstrip('/')}/v1/{path.lstrip('/')}"
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=payload, method=method)
    if token:
        request.add_header("X-Vault-Token", token)
    if payload is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise VaultError(_http_message(path, error.code, error.read())) from error
    except OSError as error:
        raise VaultError(f"cannot reach Vault at {addr}: {error}") from error

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError as error:
        raise VaultError(f"Vault returned a non-JSON body for {path}") from error
    return parsed if isinstance(parsed, dict) else {}


def _http_message(path: str, status: int, raw: bytes) -> str:
    """Say which path was refused and what Vault said about it.

    A bare "403 Forbidden" sends the reader to the wrong layer. The path is
    what identifies the missing grant.
    """
    detail = ""
    try:
        errors = json.loads(raw).get("errors")
        if isinstance(errors, list) and errors:
            detail = f": {'; '.join(str(item) for item in errors)}"
    except ValueError:
        pass
    return f"Vault returned HTTP {status} for {path}{detail}"


def login_userpass(addr: str, username: str, password: str) -> dict[str, Any]:
    """Authenticate and return the `auth` block of the response."""
    response = _request(
        addr,
        f"auth/userpass/login/{username}",
        method="POST",
        body={"password": password},
    )
    auth = response.get("auth")
    if not isinstance(auth, dict) or not auth.get("client_token"):
        raise VaultError(
            f"login at {addr} returned no token. "
            "Check the username and that the `userpass` backend is enabled."
        )
    return auth


def lookup_self(addr: str, token: str) -> dict[str, Any]:
    """The token's own metadata: policies, entity, remaining TTL."""
    data = _request(addr, "auth/token/lookup-self", token=token).get("data")
    if not isinstance(data, dict):
        raise VaultError("token lookup returned no data")
    return data


def renew_self(addr: str, token: str) -> dict[str, Any]:
    """Extend the login token. Only the Vault token is renewed; see broker.py."""
    auth = _request(addr, "auth/token/renew-self", method="POST", token=token).get("auth")
    if not isinstance(auth, dict):
        raise VaultError("token renewal returned no auth block")
    return auth


def revoke_self(addr: str, token: str) -> None:
    """Revoke the login token, and with it every lease it created."""
    _request(addr, "auth/token/revoke-self", method="POST", token=token)


def read_creds(addr: str, token: str, path: str) -> dict[str, Any]:
    """Read a credentials path, returning the whole response.

    The caller needs the top-level `lease_id`, `lease_duration` and
    `renewable` as well as `data`, and the two engines disagree about what is
    inside `data`, so the mapping is left to `broker.py`.
    """
    return _request(addr, path, token=token)


def identity_policies(lookup: dict[str, Any]) -> list[str]:
    """Policies from a lookup, INCLUDING the ones a group grants.

    Vault splits these: `policies` holds what the token was minted with,
    which for a `userpass` login with `token_policies = []` is just
    `default`. A policy attached to an identity group arrives in
    `identity_policies` instead. Reporting only `policies` tells a developer
    they have no grants when they do.
    """
    combined: list[str] = []
    for key in ("identity_policies", "policies"):
        value = lookup.get(key)
        if isinstance(value, list):
            combined.extend(str(item) for item in value)
    return sorted(set(combined))
