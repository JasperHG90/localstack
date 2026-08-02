"""`localstack logout`: revoke the session, then delete what is on disk."""

import typer

from localstack_cli.auth import vault, vault_token_file
from localstack_cli.auth.session import Session, SessionError, delete, load, session_path
from localstack_cli.commands._common import (
    fail,
    require_session,
    warn,
    warn_if_environment_shadows,
)

app = typer.Typer()


def load_session_or_none() -> Session | None:
    """The session, or None when there is none or it cannot be read.

    `logout` is the command you reach for when things are already wrong, so a
    corrupt session file must not stop it from cleaning up.
    """
    try:
        return load(session_path())
    except SessionError:
        return None


@app.command()
def logout() -> None:
    """Revoke the Vault token, which kills the brokered leases with it.

    Revoke first, delete second. Deleting the file alone leaves live tokens
    on the cluster for up to an hour, which is the whole failure this order
    prevents. If revocation fails the files still go, because a stale token
    on disk is worse than none, and the accessors print so they can be
    revoked by hand.
    """
    # `~/.vault-token` can outlive the session file. Report it, do NOT delete
    # it: without a session there is no token to revoke it WITH, so deleting
    # would drop the only local reference to a credential that stays live on
    # the cluster -- the orphan this command exists to prevent. The file may
    # also belong to a plain `vault login` and not to this CLI at all.
    if load_session_or_none() is None:
        if vault_token_file.token_path().exists():
            warn(
                "no localstack session, but ~/.vault-token exists.\n"
                "  It is not this CLI's to revoke. End it properly with:\n"
                "    VAULT_TOKEN=$(cat ~/.vault-token) vault token revoke -self "
                "&& rm ~/.vault-token"
            )
        raise fail("not logged in. Run `localstack login`.")

    session = require_session()

    revoked = True
    try:
        vault.revoke_self(session.vault_addr, session.vault.token)
    except vault.VaultError as error:
        revoked = False
        warn(f"error: could not revoke the Vault token: {error}")
        warn("These credentials are still live. Revoke them by accessor:")
        for name in ("vault", "nomad", "consul"):
            entry = session.credential(name)
            if entry is not None and entry.accessor:
                warn(f"  {name}: {entry.accessor}")

    delete(session_path())
    vault_token_file.remove()

    if revoked:
        warn(f"logged out {session.username}. Vault, Nomad and Consul tokens revoked.")

    # `logout` looks like it did nothing while the environment still holds a
    # token, so say why before the developer concludes the command is broken.
    warn_if_environment_shadows(session)

    if not revoked:
        raise typer.Exit(1)
