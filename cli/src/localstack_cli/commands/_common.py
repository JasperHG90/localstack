"""Shared plumbing for the auth commands.

Everything here writes to stderr or returns a value. Nothing prints to
stdout: `env` and `token` own stdout and their contracts are byte-exact.
"""

import sys

import typer

from localstack_cli.auth import vault, vault_token_file
from localstack_cli.auth.broker import BrokerError, ensure_fresh
from localstack_cli.auth.session import Session, SessionError, load, save, session_path


def warn(message: str) -> None:
    """Diagnostics go to stderr, always."""
    print(message, file=sys.stderr)


def fail(message: str, code: int = 1) -> typer.Exit:
    warn(f"error: {message}")
    return typer.Exit(code)


def require_session() -> Session:
    """Load the session or exit with a message naming the fix."""
    try:
        session = load(session_path())
    except SessionError as error:
        raise fail(str(error)) from error
    if session is None:
        raise fail("not logged in. Run `localstack login`.")
    return session


def refreshed_session(session: Session) -> Session:
    """Bring every credential inside its skew window, persisting any change."""
    try:
        updated, changed = ensure_fresh(session)
    except BrokerError as error:
        raise fail(str(error)) from error
    if changed:
        save(updated, session_path())
    return updated


def warn_if_environment_shadows(session: Session) -> None:
    """Say out loud that a bare `vault` is not using this session.

    The devcontainer injects `VAULT_TOKEN` into every shell, so this is the
    normal case here rather than an edge one, and it fails in the direction
    nobody notices: the developer believes they are `operator` and they are
    root.
    """
    other = vault_token_file.env_token_differs(session.vault.token)
    if other is None:
        return

    detail = ""
    try:
        policies = vault.identity_policies(vault.lookup_self(session.vault_addr, other))
        if policies:
            detail = f" It carries: {', '.join(policies)}."
    except vault.VaultError:
        # Not being able to describe the other token does not make the
        # mismatch less true, and the warning is the point.
        pass

    warn(
        f"WARNING: VAULT_TOKEN is set in this shell and is NOT this session's token.\n"
        f"  A bare `vault` command runs as that token, not as {session.username}.{detail}\n"
        '  Fix it for this shell:  eval "$(localstack env)"\n'
        "  Or use the `vault` shim on PATH (`localstack deps --with-shims`)."
    )
