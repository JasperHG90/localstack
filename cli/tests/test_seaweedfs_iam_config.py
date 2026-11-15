"""SeaweedFS's workload-identity config binds each role to one job and one bucket.

The config is rendered for real: Terraform evaluates `local.seaweedfs_iam` and
the jobspec template offline, the Vault action is replaced by a stand-in key,
and the result is parsed as the JSON SeaweedFS loads. A role whose trust policy
lacked either job condition would let any job assume it
(spike:seaweedfs-workload-identity/2).
"""

import json
from typing import Any

import pytest

from tests.fixtures.seaweedfs_iam import JOBSPEC, SIGNING_KEY, render_iam

KEYLESS_JOBS = {
    "tempo": "tempo",
    "loki": "loki",
    "registry": "registry",
    "ov-sync-consumer": "ov-sync",
}
ISSUER = "https://nomad.lab.orangecluster.nl"


@pytest.fixture(scope="module")
def iam(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return render_iam(tmp_path_factory.mktemp("iam"))


def _nomad_roles(iam: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        r
        for r in iam["roles"]
        if r["trustPolicy"]["Statement"][0]["Principal"]["Federated"] == "nomad"
    ]


def test_weed_server_loads_the_iam_config() -> None:
    assert '"-s3.iam.config=/secrets/iam.json"' in JOBSPEC.read_text()


def test_default_effect_is_deny(iam: dict[str, Any]) -> None:
    assert iam["policy"] == {"defaultEffect": "Deny"}


def test_sts_signing_key_comes_from_vault(iam: dict[str, Any]) -> None:
    assert iam["sts"]["signingKey"] == SIGNING_KEY


def test_providers_are_nomad_and_vault_with_audience_seaweedfs(iam: dict[str, Any]) -> None:
    assert {p["name"]: p["config"] for p in iam["providers"]} == {
        "nomad": {"issuer": ISSUER, "clientId": "seaweedfs"},
        "vault": {
            "issuer": "https://vault.lab.orangecluster.nl/v1/identity/oidc",
            "clientId": "seaweedfs",
        },
    }
    assert "policyClaim" not in json.dumps(iam["providers"]), (
        "claim mode splits on commas: evil,tempo got tempo"
    )


def test_one_role_per_keyless_job(iam: dict[str, Any]) -> None:
    assert {r["roleName"]: r["attachedPolicies"] for r in _nomad_roles(iam)} == {
        job: [job] for job in KEYLESS_JOBS
    }


@pytest.mark.parametrize("job", sorted(KEYLESS_JOBS))
def test_role_trusts_only_its_job(iam: dict[str, Any], job: str) -> None:
    role = next(r for r in iam["roles"] if r["roleName"] == job)
    [statement] = role["trustPolicy"]["Statement"]
    assert statement["Principal"] == {"Federated": "nomad"}
    assert statement["Condition"] == {
        "StringEquals": {"oidc:nomad_job_id": job},
        "StringLike": {"oidc:sub": f"global:default:{job}:*"},
    }


@pytest.mark.parametrize("job", sorted(KEYLESS_JOBS))
def test_policy_reaches_only_its_bucket(iam: dict[str, Any], job: str) -> None:
    policy = next(p for p in iam["policies"] if p["name"] == job)
    resources = [r for s in policy["document"]["Statement"] for r in s["Resource"]]
    bucket = KEYLESS_JOBS[job]
    assert sorted(resources) == [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]
