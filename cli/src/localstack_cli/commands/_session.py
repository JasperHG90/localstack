"""Turning a denial into the right sentence.

There are two ways to be told no, and they need opposite responses. A dead
session means log in again. A missing grant means the policy does not allow
this, and logging in again changes nothing, so saying "log in" sends the
developer round in a circle.

Vault can be asked directly: `auth/token/lookup-self` answering 200 while the
real call answers 403 proves the session is live and the policy is not.
Nomad has no equivalent, so the plan's probe stands in: a 403 on the job list
while a known single job reads fine means the token lacks `list-jobs`
specifically.

Both probes run only after a 403, never on the success path.
"""

import typer

from localstack_cli.api import nomad, vault
from localstack_cli.api.errors import ClusterError, MissingCapability, NotAuthenticated
from localstack_cli.commands._common import fail

# The ticket that grants each denied read, so the message names a fix rather
# than just a problem.
GRANTED_BY = {
    vault.POLICY_READ: "the `developer` Vault policy (F11)",
    vault.METADATA_READ: "the `developer` Vault policy (F11)",
    nomad.LIST_JOBS: "brokering `nomad/creds/manage` (D2)",
    nomad.NODE_READ: "brokering `nomad/creds/manage` (D2)",
}


def explain(
    error: ClusterError,
    vault_addr: str,
    vault_token: str | None,
    nomad_addr: str | None = None,
    nomad_token: str | None = None,
    known_job: str = "haproxy",
) -> typer.Exit:
    """One message for a denial, naming the fix.

    Returns the `typer.Exit` to raise, so the caller keeps the `raise`
    visible at the call site.
    """
    if isinstance(error, NotAuthenticated):
        return fail(f"{error.service}: no usable session. Run `localstack login`.")

    if isinstance(error, MissingCapability):
        live = _session_is_live(
            error.service, vault_addr, vault_token, nomad_addr, nomad_token, known_job
        )
        granted = GRANTED_BY.get(error.capability, "a policy grant")

        if live is False:
            # The 403 looked like a policy gap, but the service says the token
            # does not authenticate. The probe wins: telling someone their
            # policy is short when their session is dead is the same circle
            # this function exists to break, pointed the other way.
            return fail(
                f"{error.service}: the token does not authenticate. Run `localstack login`."
            )

        if live is True:
            return fail(
                f"{error.service}: the session is live but the token lacks "
                f"{error.capability}. That comes from {granted}. Logging in again "
                "will not change it."
            )

        # Nothing to probe with, so neither claim is safe to make.
        return fail(f"{error.service}: denied {error.capability}. That comes from {granted}.")

    return fail(str(error))


def _session_is_live(
    service: str,
    vault_addr: str,
    vault_token: str | None,
    nomad_addr: str | None,
    nomad_token: str | None,
    known_job: str,
) -> bool | None:
    """Whether the token authenticates, asked the way each service allows.

    `None` means the question could not be put: no token, or no address to
    ask. That is a third answer, not a `False`, because "we could not check"
    and "the token is dead" lead to opposite advice.

    Only ever called after a 403, never on the success path.
    """
    if service == "vault":
        return vault.token_is_live(vault_addr, vault_token) if vault_token else None
    if service == "nomad":
        return nomad_reads_a_known_job(nomad_addr, nomad_token, known_job) if nomad_addr else None
    return None


def nomad_reads_a_known_job(address: str, token: str | None, known_job: str) -> bool | None:
    """`True` when a known single job still reads, `None` when it does not.

    Never `False`, and that asymmetry is the point. A successful probe proves
    the token authenticates, so the 403 that prompted it was a policy gap. A
    failed probe proves nothing: it could be a dead token or a second policy
    gap, and Nomad's dead-token case is already classified upstream, where
    the body says `ACL token not found`. Returning `False` here would turn
    an ordinary missing capability into "your session is dead", which is the
    same wrong turn this module exists to prevent.
    """
    try:
        nomad.get_job(address, token, known_job)
    except ClusterError:
        return None
    return True
