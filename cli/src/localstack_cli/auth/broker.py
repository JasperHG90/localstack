"""Brokering the Nomad and Consul tokens from a Vault session.

The two secret engines return different field names for the same two things,
measured against the live cluster on 2026-08-02:

    nomad/creds/deploy   data.secret_id   data.accessor_id
    consul/creds/deploy  data.token       data.accessor

Both carry the lease at the top level (`lease_id`, `lease_duration`,
`renewable`). That mapping lives here and nowhere else.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from localstack_cli.auth import vault
from localstack_cli.auth.session import (
    DEFAULT_SKEW,
    Credential,
    Session,
    expires_at,
)

NOMAD_CREDS_PATH = "nomad/creds/deploy"
NOMAD_MANAGE_CREDS_PATH = "nomad/creds/manage"
CONSUL_CREDS_PATH = "consul/creds/deploy"

# Which response field holds the token and which holds the accessor, per
# engine. A table rather than two near-identical functions, so adding a third
# engine is a row.
_FIELDS = {
    "nomad": (NOMAD_CREDS_PATH, "secret_id", "accessor_id"),
    "nomad_manage": (NOMAD_MANAGE_CREDS_PATH, "secret_id", "accessor_id"),
    "consul": (CONSUL_CREDS_PATH, "token", "accessor"),
}


class BrokerError(RuntimeError):
    """Brokering failed, with a message naming the path and the likely grant."""


def _denied_message(service: str, path: str, policies: list[str], detail: str) -> str:
    return (
        f"denied reading {path} for the {service} token.\n"
        f"  Vault said: {detail}\n"
        f"  Your policies are: {', '.join(policies) if policies else '(none beyond default)'}\n"
        "  The grant lives in F11-foundation-human-read-role, which binds "
        "`developer` to the three creds paths through an identity group."
    )


def broker(service: str, addr: str, vault_token: str, now: datetime | None = None) -> Credential:
    """Read one creds path and map it into a cache entry."""
    try:
        path, token_field, accessor_field = _FIELDS[service]
    except KeyError:
        raise BrokerError(f"unknown service {service!r}") from None

    try:
        response = vault.read_creds(addr, vault_token, path)
    except vault.VaultError as error:
        message = str(error)
        if "HTTP 403" in message:
            policies: list[str] = []
            try:
                policies = vault.identity_policies(vault.lookup_self(addr, vault_token))
            except vault.VaultError:
                # The lookup is a courtesy. Its failure must not replace the
                # 403 with a less useful error about the lookup.
                pass
            raise BrokerError(_denied_message(service, path, policies, message)) from error
        raise BrokerError(message) from error

    data = response.get("data")
    if not isinstance(data, dict):
        raise BrokerError(f"{path} returned no data")
    token = data.get(token_field)
    accessor = data.get(accessor_field)
    if not token or not accessor:
        raise BrokerError(
            f"{path} returned no `{token_field}`/`{accessor_field}`. "
            "The secret engine's response shape may have changed."
        )

    return Credential(
        token=str(token),
        accessor=str(accessor),
        expires_at=expires_at(int(response.get("lease_duration", 0)), now),
        renewable=bool(response.get("renewable", False)),
        lease_id=str(response.get("lease_id", "")),
    )


def credential_from_login(auth: dict[str, Any], now: datetime | None = None) -> Credential:
    """Map a `userpass` login response into the Vault entry.

    Policies come from the UNION, not from `token_policies`. Measured against
    the live cluster: a `userpass` login returns
    `token_policies ['default']`, `identity_policies ['developer']` and
    `policies ['default', 'developer']`. F2 sets `token_policies = []` and F11
    grants through an identity group, so storing `token_policies` alone makes
    `whoami` report `default` to a developer who actually holds `developer` --
    the same misreading R8 forbids in the 403 message.
    """
    granted = vault.identity_policies(auth)
    return Credential(
        token=str(auth["client_token"]),
        accessor=str(auth.get("accessor", "")),
        expires_at=expires_at(int(auth.get("lease_duration", 0)), now),
        renewable=bool(auth.get("renewable", False)),
        entity_id=str(auth.get("entity_id", "")),
        policies=tuple(granted),
    )


def ensure_fresh(
    session: Session,
    now: datetime | None = None,
    skew: timedelta = DEFAULT_SKEW,
) -> tuple[Session, bool]:
    """Renew the Vault token, re-broker the other two, and say whether anything moved.

    The asymmetry is deliberate and the reason is in the lease config:
    brokered leases cap at `max_ttl 3600`, so renewing one buys at most a
    single extra window and then fails anyway. Re-brokering is unbounded.
    The Vault token is the opposite, so it is renewed.

    Superseded leases are left to expire. Revoking one needs
    `sys/leases/revoke`, which the `default` policy does not grant, so this
    cannot revoke them and must not pretend to. Do not "fix" this by adding
    the call; add the grant first or it will 403 in the middle of a refresh.
    """
    moment = now if now is not None else datetime.now(UTC)
    changed = False

    vault_entry = session.vault
    if vault_entry.is_stale(moment, skew):
        if not vault_entry.renewable:
            raise BrokerError("session expired, run `localstack login`")
        try:
            auth = vault.renew_self(session.vault_addr, vault_entry.token)
        except vault.VaultError as error:
            raise BrokerError("session expired, run `localstack login`") from error
        vault_entry = replace(
            vault_entry,
            expires_at=expires_at(int(auth.get("lease_duration", 0)), moment),
            renewable=bool(auth.get("renewable", vault_entry.renewable)),
        )
        changed = True

    refreshed: dict[str, Credential | None] = {}
    for service in ("nomad", "nomad_manage", "consul"):
        entry = session.credential(service)
        if entry is not None and not entry.is_stale(moment, skew):
            refreshed[service] = entry
            continue
        refreshed[service] = broker(service, session.vault_addr, vault_entry.token, moment)
        changed = True

    return (
        replace(
            session,
            vault=vault_entry,
            nomad=refreshed["nomad"],
            nomad_manage=refreshed["nomad_manage"],
            consul=refreshed["consul"],
        ),
        changed,
    )
