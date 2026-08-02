"""`~/.vault-token`: the file the stock `vault` CLI reads, and what outranks it.

This CLI does not own this file, which is why it lives in its own module
rather than inside `session.py`. `vault login` writes it, so writing it here
is not a novel invention.

**It is inert while `VAULT_TOKEN` is set**, and the devcontainer sets it for
every shell. That is not a detail: it means a developer who has logged in is
still running as the injected root token, silently and in the direction of
more privilege. `env_token_differs` is how the commands say so out loud.
"""

import os
import tempfile
from pathlib import Path

VAULT_TOKEN = "VAULT_TOKEN"


def token_path() -> Path:
    return Path.home() / ".vault-token"


def current_token() -> str | None:
    """The token a bare `vault` command would use, or None.

    `VAULT_TOKEN` beats the file. Measured, and it matches the Vault CLI's
    own order. This is the single definition of that precedence: the banner's
    session dot and R11's warning both read it here, because two copies would
    let them disagree about the one thing the warning exists to report.
    """
    from_env = os.environ.get(VAULT_TOKEN)
    if from_env:
        return from_env
    try:
        return token_path().read_text().strip() or None
    except OSError:
        return None


def write(token: str) -> Path:
    """Write the token at 0600, with the mode set at creation.

    `mkstemp` is what sets that mode, and it is why the write is a temp file
    plus a rename: a chmod after writing leaves a window in which the token is
    world-readable, and a hand-picked temp name can collide.
    """
    path = token_path()
    # See session.py: mkstemp creates 0600 with O_EXCL under a name nothing
    # else holds, so a leftover temp file cannot block a later write.
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".vault-token.")
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(token)
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return path


def remove() -> bool:
    """Delete the file. True when there was one.

    `logout` deletes rather than blanking it: a revoked token left on disk
    makes the next `vault` command fail with a confusing 403 instead of an
    honest "not logged in".
    """
    try:
        token_path().unlink()
        return True
    except FileNotFoundError:
        return False


def env_token_differs(session_token: str) -> str | None:
    """The environment's token when it would shadow the session, else None.

    Returns None when `VAULT_TOKEN` is unset, and when it equals the session
    token, which is the state after `eval "$(localstack env)"`. A warning
    that fires on every healthy session teaches people to ignore it.
    """
    from_env = os.environ.get(VAULT_TOKEN)
    if not from_env or from_env == session_token:
        return None
    return from_env
