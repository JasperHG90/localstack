"""SeaweedFS's workload-identity config binds each role to one job and one bucket.

The config is rendered for real: Terraform evaluates `local.seaweedfs_iam` and
the jobspec template offline, the Vault action is replaced by a stand-in key,
and the result is parsed as the JSON SeaweedFS loads. A role whose trust policy
lacked either job condition would let any job assume it
(spike:seaweedfs-workload-identity/2).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "deployments" / "infrastructure"
JOBSPEC = INFRA / "services" / "seaweedfs.hcl"

KEYLESS_JOBS = {
    "tempo": "tempo",
    "loki": "loki",
    "registry": "registry",
    "ov-sync-consumer": "ov-sync",
}
ISSUER = "https://nomad.lab.orangecluster.nl"
STS_SECRET = "secret/data/default/seaweedfs/sts"


@pytest.fixture(scope="module")
def iam(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    terraform = shutil.which("terraform")
    if terraform is None:
        pytest.fail("terraform is not on PATH; this test renders the config with it")
    services = (INFRA / "services.tf").read_text()
    locals_block = re.search(r"^locals \{\n  seaweedfs_keyless_jobs.*?^\}\n", services, re.M | re.S)
    job = re.search(r'^resource "nomad_job" "seaweedfs" \{\n(.*?)^\}\n', services, re.M | re.S)
    if not locals_block or not job:
        pytest.fail("services.tf has no seaweedfs_keyless_jobs locals or no nomad_job.seaweedfs")
    sts_name = re.search(
        r'resource "vault_kv_secret_v2" "seaweedfs_sts" \{[^}]*name\s*=\s*"([^"]+)"',
        (INFRA / "secrets.tf").read_text(),
    )
    assert sts_name and f"secret/data/{sts_name.group(1)}" == STS_SECRET, (
        "the STS signing key is not written to default/seaweedfs/sts"
    )
    # nomad_job.seaweedfs's own templatefile call, with its three resource
    # references swapped for the paths they resolve to.
    call = (
        job.group(1)
        .replace("vault_kv_secret_v2.seaweedfs_sts.path", f'"{STS_SECRET}"')
        .replace("vault_kv_secret_v2.seaweedfs_admin.path", '"secret/data/default/seaweedfs/admin"')
        .replace(
            "vault_kv_secret_v2.seaweedfs_webhook.path", '"secret/data/default/seaweedfs/webhook"'
        )
        .replace("jobspec = templatefile(", "rendered = templatefile(", 1)
    )
    if "vault_kv_secret_v2." in call:
        pytest.fail("nomad_job.seaweedfs passes a resource reference this test does not resolve")
    workdir = tmp_path_factory.mktemp("iam")
    (workdir / "services").mkdir()
    shutil.copy(JOBSPEC, workdir / "services" / "seaweedfs.hcl")
    (workdir / "main.tf").write_text(locals_block.group(0) + "\nlocals {\n" + call + "}\n")
    # jsonencode makes the console print one JSON string literal.
    printed = subprocess.run(
        [terraform, "console"],
        input="jsonencode(local.rendered)\n",
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    jobspec = json.loads(json.loads(printed))
    template = re.search(
        r"data\s*=\s*<<-EOH\n\s*(\{\{ with secret[^\n]*)\n\s*EOH\n"
        r'\s*destination\s*=\s*"secrets/iam\.json"',
        jobspec,
        re.S,
    )
    if not template:
        pytest.fail("seaweedfs.hcl renders no template with destination secrets/iam.json")
    body = template.group(1)
    opener = f'{{{{ with secret "{STS_SECRET}" }}}}'
    assert body.startswith(opener), (
        "the IAM config does not read its signing key from default/seaweedfs/sts"
    )
    body = body.removeprefix(opener).removesuffix("{{ end }}")
    config: dict[str, Any] = json.loads(
        body.replace("{{ .Data.data.signing_key }}", "c3RhbmQtaW4=")
    )
    return config


def test_weed_server_loads_the_iam_config() -> None:
    assert '"-s3.iam.config=/secrets/iam.json"' in JOBSPEC.read_text()


def test_default_effect_is_deny(iam: dict[str, Any]) -> None:
    assert iam["policy"] == {"defaultEffect": "Deny"}


def test_sts_signing_key_comes_from_vault(iam: dict[str, Any]) -> None:
    assert iam["sts"]["signingKey"] == "c3RhbmQtaW4="


def test_nomad_is_the_only_provider_with_audience_seaweedfs(iam: dict[str, Any]) -> None:
    assert len(iam["providers"]) == 1
    provider = iam["providers"][0]
    assert provider["config"] == {"issuer": ISSUER, "clientId": "seaweedfs"}
    assert "policyClaim" not in json.dumps(provider), (
        "claim mode splits on commas: evil,tempo got tempo"
    )


def test_one_role_per_keyless_job(iam: dict[str, Any]) -> None:
    assert {r["roleName"]: r["attachedPolicies"] for r in iam["roles"]} == {
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
