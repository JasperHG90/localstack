"""`localstack login`: authenticate to Vault and broker the other two tokens."""

import getpass
import os

import typer

from localstack_cli.auth import vault, vault_token_file
from localstack_cli.auth.broker import BrokerError, broker, credential_from_login
from localstack_cli.auth.session import Session, SessionError, load, save, session_path
from localstack_cli.commands._common import fail, warn, warn_if_environment_shadows

app = typer.Typer()

USERNAME_ENV = "LOCALSTACK_VAULT_USERNAME"


def _revoke_quietly(addr: str, token: str) -> bool:
    """Revoke a token we are about to stop tracking. True when it worked.

    Failure is not fatal anywhere this is called: the token may already be
    expired or revoked, and the caller has a more important error to report.
    """
    try:
        vault.revoke_self(addr, token)
        return True
    except vault.VaultError:
        return False


def _load_previous() -> Session | None:
    """The session this login will replace, read BEFORE anything overwrites it."""
    try:
        return load(session_path())
    except SessionError:
        # An unreadable session file still gets replaced; there is simply no
        # token in it we could revoke.
        return None


def _revoke_previous(previous: Session | None) -> None:
    """End the replaced session, once the new one is safely on disk."""
    if previous is None:
        return
    if _revoke_quietly(previous.vault_addr, previous.vault.token):
        warn(f"revoked the previous session for {previous.username}.")
    else:
        warn(
            f"could not revoke the previous session for {previous.username} "
            f"(accessor {previous.vault.accessor}). It may already be gone."
        )


@app.command()
def login(
    username: str = typer.Option(
        "",
        "--username",
        "-u",
        help="Vault userpass username. Defaults to $LOCALSTACK_VAULT_USERNAME, then `operator`.",
    ),
    method: str = typer.Option("userpass", "--method", help="Auth method. Only `userpass` today."),
    vault_addr: str = typer.Option("", "--vault-addr", help="Overrides $VAULT_ADDR."),
    insecure: bool = typer.Option(
        False, "--insecure", help="Allow sending the password over plaintext HTTP."
    ),
) -> None:
    """Log in to Vault and broker the Nomad and Consul tokens in the same run.

    Brokering is eager on purpose: a missing grant then fails here, with a
    message naming the path, instead of inside a later `terraform apply`.
    """
    if method != "userpass":
        raise fail(f"unsupported method {method!r}. Only `userpass` is implemented.")

    who = username or os.environ.get(USERNAME_ENV) or "operator"
    addr = vault_addr or os.environ.get("VAULT_ADDR") or ""
    if not addr:
        raise fail("no Vault address. Set VAULT_ADDR or pass --vault-addr.")

    # Before the prompt, so a refused address never collects a password.
    try:
        warning = vault.guard_address(addr, insecure)
    except vault.InsecureAddressError as error:
        raise fail(str(error)) from error
    if warning:
        warn(warning)

    # Read before anything can overwrite it: `save()` below replaces the file
    # this would be read from, so the old token has to be captured first.
    previous = _load_previous()

    password = getpass.getpass(f"Password for {who} at {addr}: ")

    try:
        auth = vault.login_userpass(addr, who, password)
    except vault.VaultError as error:
        # NOTHING has been touched yet, and that is deliberate. An earlier
        # revision ended the previous session before this call, so a mistyped
        # password destroyed a working one and left the cache holding a dead
        # token. A failed login must leave the existing session alone.
        raise fail(str(error)) from error
    del password

    vault_credential = credential_from_login(auth)

    try:
        session = Session(
            method=method,
            vault_addr=addr,
            username=who,
            vault=vault_credential,
            nomad=broker("nomad", addr, vault_credential.token),
            consul=broker("consul", addr, vault_credential.token),
        )
    except BrokerError as error:
        # The Vault login itself worked, and saying so matters: the fix is a
        # policy grant, not a password. But nothing will persist this token,
        # so revoke it rather than leave an untracked credential behind. Every
        # retry against a missing grant would otherwise add another. The
        # previous session is untouched and still usable.
        warn(f"logged in as {who}, but brokering failed. Revoking that token.")
        _revoke_quietly(addr, vault_credential.token)
        raise fail(str(error)) from error

    # Persist the new session BEFORE ending the old one. Revoking first opens a
    # window between the revoke and the write where a crash leaves the NEW
    # token live with nothing referencing it AND no session on disk: logged
    # out, holding an orphan. This order is strictly better. A crash in the
    # remaining window orphans the OLD token, which is the state that existed
    # before any of this, and the developer still has a working session.
    save(session, session_path())
    vault_token_file.write(session.vault.token)

    # Overwriting the cache without revoking leaves the old token live for its
    # full TTL, weeks by default, with nothing holding a reference to it. Ten
    # such orphans were found on this cluster while implementing D2.
    _revoke_previous(previous)

    warn(f"logged in as {who} ({session.vault.entity_id or 'no entity'}).")
    warn_if_environment_shadows(session)
