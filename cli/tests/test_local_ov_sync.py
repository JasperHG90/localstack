"""The operator's local ov-sync route: one Vault token role, one consumer prefix.

`ovsq` on a laptop writes `ov-sync/JasperHG90/local/` with STS credentials
minted from the operator's own Vault session (`localstack token s3 local-ov-sync`). Only
the operator entity may mint the token, and the consumer maps the prefix to a
folder of its own: its catch-up pass deletes every file under a mapped folder
that has no object behind it, so a folder mapped over another would empty it.
"""

import re
from pathlib import Path

from tests.fixtures.seaweedfs_iam import REPO_ROOT, block

INFRA = REPO_ROOT / "deployments" / "infrastructure"
APPS = REPO_ROOT / "deployments" / "applications"
HERMES_ROOT = "viking://user/jasper/resources/"
LOCAL_ROOT = "viking://user/jasper/resources/local/"


def _read(path: Path) -> str:
    return path.read_text()


def test_vault_token_role_is_short_lived_and_carries_the_local_claim() -> None:
    role = block(_read(INFRA / "oidc.tf"), 'resource "vault_identity_oidc_role" "local_ov_sync" {')
    assert re.search(r'name\s*=\s*"local-ov-sync"', role)
    assert re.search(r"client_id\s*=\s*local\.seaweedfs_audience", role)
    assert re.search(r"ttl\s*=\s*900\b", role)
    assert re.search(
        r"template\s*=\s*jsonencode\(\{\s*local_ov_sync\s*=\s*local\.local_ov_sync_prefix\s*\}\)",
        role,
    )
    services = _read(INFRA / "services.tf")
    assert re.search(r'local_ov_sync_prefix\s*=\s*"JasperHG90/local"', services)


def test_vault_policy_reads_only_the_local_token_path() -> None:
    policy = block(_read(INFRA / "identity.tf"), 'resource "vault_policy" "local_ov_sync" {')
    paths = re.findall(r'path\s+"([^"]+)"', policy)
    assert paths == ["identity/oidc/token/${vault_identity_oidc_role.local_ov_sync.name}"]
    assert re.findall(r"capabilities\s*=\s*\[([^\]]*)\]", policy) == ['"read"']


def test_vault_group_holds_only_the_operator_entity() -> None:
    group = block(_read(INFRA / "identity.tf"), 'resource "vault_identity_group" "local_ov_sync" {')
    assert re.search(r'type\s*=\s*"internal"', group)
    assert re.search(r"policies\s*=\s*\[vault_policy\.local_ov_sync\.name\]", group)
    members = re.search(r"member_entity_ids\s*=\s*\[([^\]]*)\]", group)
    assert members and members.group(1).strip() == "vault_identity_entity.operator.id"


def _prefixes() -> dict[str, str]:
    services = _read(APPS / "services.tf")
    job = block(services, 'resource "nomad_job" "ov_sync_consumer" {')
    body = re.search(r"prefixes\s*=\s*jsonencode\(\{(.*?)\}\)", job, re.S)
    assert body, "nomad_job.ov_sync_consumer has no prefixes map"
    pairs = re.findall(r'"([^"]+)"\s*=\s*"([^"]+)"', body.group(1))
    return dict(pairs)


def test_consumer_prefix_maps_local_to_its_own_folder() -> None:
    assert _prefixes()["JasperHG90/local/"] == LOCAL_ROOT


def test_no_consumer_prefix_folder_contains_another_or_the_hermes_root() -> None:
    roots = list(_prefixes().values())
    above = [r for r in roots if HERMES_ROOT.startswith(r)]
    assert not above, f"{above} holds the hermes root: catch-up would delete every save"
    for root in roots:
        others = [o for o in roots if o != root and o.startswith(root)]
        assert not others, f"{root} contains {others}: catch-up would delete them"
