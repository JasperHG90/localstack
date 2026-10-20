"""Drift tests: the registry logs in to SeaweedFS keylessly through its own role.

SeaweedFS refuses an exchange without RoleArn and RoleSessionName
(spike:seaweedfs-workload-identity/3), and the helper is the registry's only
way to get S3 credentials, so a dropped parameter stops every push and pull.
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "deployments" / "applications" / "services" / "registry.hcl"
SERVICES = REPO_ROOT / "deployments" / "applications" / "services.tf"


def test_identity_is_for_seaweedfs() -> None:
    identity = re.search(r"identity \{(.*?)\}", REGISTRY.read_text(), re.S)
    assert identity, "registry.hcl has no identity block"
    assert re.search(r'aud\s*=\s*\["seaweedfs"\]', identity.group(1))
    assert 'filepath    = "secrets/nomad_seaweedfs.jwt"' in identity.group(1)


def test_helper_names_its_role_and_session() -> None:
    text = REGISTRY.read_text()
    url = re.search(r'"http://\$\{s3_host\}:8333/\?Action=AssumeRoleWithWebIdentity[^"]*"', text)
    assert url, "the registry's credential helper does not call SeaweedFS's STS"
    assert "RoleArn=arn:aws:iam::role/registry" in url.group(0)
    assert "RoleSessionName=registry" in url.group(0)
    assert "cat /secrets/nomad_seaweedfs.jwt" in text


def test_region_endpoint_follows_the_lookup() -> None:
    text = REGISTRY.read_text()
    assert "192.168.2.29:9000" not in text
    assert "regionendpoint: http://${s3_host}:8333" in text
    job = re.search(r'resource "nomad_job" "registry" \{(.*?)\n\}', SERVICES.read_text(), re.S)
    assert job, 'services.tf has no resource "nomad_job" "registry"'
    assert (
        "s3_host              = data.consul_service.seaweedfs.service[0].node_address"
        in job.group(1)
    )
