"""The fetchers against the real cluster.

Marked `cluster` and excluded from the default run. Run on purpose:

    uv run --project cli pytest -m cluster

These go over the HTTPS edge hostnames, which answer from the LAN and the
tailnet and survive the firewall change that closes the plaintext ports.
"""

import os

import pytest

from localstack_cli.api import consul, nomad, vault
from localstack_cli.api.errors import MissingCapability

pytestmark = pytest.mark.cluster

EDGE = {
    "vault": "https://vault.lab.orangecluster.nl",
    "nomad": "https://nomad.lab.orangecluster.nl",
    "consul": "https://consul.lab.orangecluster.nl",
}


def test_vault_seal_status_needs_no_token() -> None:
    status = vault.seal_status(EDGE["vault"], timeout=10)

    assert status.shares > 0
    assert status.threshold > 0


def test_consul_health_reads_tokenless() -> None:
    checks = consul.list_checks(EDGE["consul"], timeout=10)

    assert checks


def test_nomad_reads_need_a_token_that_can_list_jobs() -> None:
    """The precondition, made legible.

    This needs a Nomad token carrying `list-jobs` and `node:read`. The
    `nomad/creds/deploy` role the CLI brokers today grants neither, so until
    `nomad/creds/manage` is brokered too this fails with the capability it
    wanted, which is exactly what the panel renders.
    """
    token = os.environ.get("NOMAD_TOKEN")
    if not token:
        pytest.skip("no NOMAD_TOKEN in the environment")

    try:
        jobs = nomad.job_statuses(EDGE["nomad"], token, timeout=10)
        nodes = nomad.list_nodes(EDGE["nomad"], token, timeout=10)
    except MissingCapability as denied:
        pytest.fail(
            f"the token cannot drive the panel: {denied}. "
            "Broker `nomad/creds/manage` so the CLI holds a token that can read."
        )

    assert jobs
    assert nodes
