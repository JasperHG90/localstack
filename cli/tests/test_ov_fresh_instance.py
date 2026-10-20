"""Drift tests: OpenViking runs on the v2 store and the old store stays a backup.

OpenViking moved to bucket `openviking-v2`, schema `openviking_v2` and host
volume `openviking_data_v2`. The old bucket, schema and volume are kept as a
read-only backup, and what keeps the bucket read-only is that the `openviking`
storage user's policy names only the new bucket.
"""

import json
import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"
INFRA = REPO_ROOT / "deployments" / "infrastructure"
CONFIG = APPS / "services" / "openviking" / "ov.conf.json"
JOBSPEC = APPS / "services" / "openviking.hcl"
STORAGE = APPS / "storage.tf"
BACKUP = INFRA / "services" / "backup-s3.hcl"
README = APPS / "services" / "openviking" / "README.md"

SYNC_LINE = re.compile(
    r"^\s*rclone sync seaweedfs:(\S+) gcs:\$\{gcs_bucket\}/minio/([^/\s]+)/ .*$", re.M
)


def _block(text: str, header: str) -> str:
    """The body of the block opened by `header`, found by brace depth."""
    start = text.find(header)
    if start == -1:
        pytest.fail(f"no `{header}` block — the check cannot run")
    depth = 0
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0 and text[i] == "}":
            return text[start : i + 1]
    pytest.fail(f"`{header}` block never closes")


def _bucket_users(storage: str) -> dict[str, dict[str, list[str]]]:
    """Each bucket in `local.buckets`, with the user names of its writers and readers."""
    catalog = _block(storage, "buckets = {")
    found: dict[str, dict[str, list[str]]] = {}
    for key in re.finditer(r'^    "?([A-Za-z0-9_-]+)"? = \{', catalog, re.M):
        body = _block(catalog[key.start() :], key.group(0).strip())
        found[key.group(1)] = {}
        for role in ("writers", "readers"):
            listed = re.search(rf"{role} = \[(.*?)\]", body, re.S)
            found[key.group(1)][role] = (
                re.findall(r'"name"\s*=\s*"([^"]+)"', listed.group(1)) if listed else []
            )
    if not found:
        pytest.fail("parsed no buckets from `local.buckets`")
    return found


def _durable(storage: str) -> set[str]:
    match = re.search(r"seaweedfs_durable_buckets\s*=\s*\[([^\]]*)\]", storage)
    if not match:
        pytest.fail("storage.tf has no seaweedfs_durable_buckets local")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_openviking_uses_the_v2_store() -> None:
    conf = json.loads(CONFIG.read_text())
    assert conf["storage"]["agfs"]["s3"]["bucket"] == "openviking-v2"
    assert conf["storage"]["vectordb"]["custom_params"]["schema"] == "openviking_v2"

    jobspec = JOBSPEC.read_text()
    deltas = re.search(r'^\s*OV_REFLECT_DELTAS_SCHEMA\s*=\s*"([^"]+)"', jobspec, re.M)
    assert deltas, "openviking.hcl sets no OV_REFLECT_DELTAS_SCHEMA"
    assert deltas.group(1) == "openviking_v2"

    volume = _block(jobspec, 'volume "openviking_data" {')
    source = re.search(r'source\s*=\s*"([^"]+)"', volume)
    assert source, "the openviking_data volume has no source"
    assert source.group(1) == "openviking_data_v2"

    services = (INFRA / "services.tf").read_text()
    created = _block(services, 'resource "nomad_dynamic_host_volume" "openviking_data_v2" {')
    assert 'name      = "openviking_data_v2"' in created


def test_old_bucket_is_read_only_for_openviking() -> None:
    storage = STORAGE.read_text()
    users = _bucket_users(storage)
    holders = [bucket for bucket, roles in users.items() if "openviking" in roles["writers"]]
    readers = [bucket for bucket, roles in users.items() if "openviking" in roles["readers"]]
    assert holders == ["openviking-v2"], f"user openviking writes {holders}"
    assert readers == [], f"user openviking reads {readers}"
    assert users["openviking"] == {"writers": [], "readers": []}, (
        "the old openviking bucket still grants some user access"
    )
    assert {"openviking", "openviking-v2"} <= _durable(storage), (
        "the backup user does not read both OpenViking buckets"
    )


def test_v2_bucket_has_its_own_backup_prefix() -> None:
    lines = list(SYNC_LINE.finditer(BACKUP.read_text()))
    if not lines:
        pytest.fail("parser found no rclone sync line in backup-s3.hcl")
    v2 = [line for line in lines if line.group(1) == "openviking-v2"]
    assert len(v2) == 1, f"backup-s3.hcl syncs openviking-v2 {len(v2)} times, want 1"
    assert v2[0].group(2) == "openviking-v2"
    into_v2 = [line.group(1) for line in lines if line.group(2) == "openviking-v2"]
    assert into_v2 == ["openviking-v2"], f"minio/openviking-v2/ is written by {into_v2}"


def test_only_jasper_consumes_openviking() -> None:
    variables = (INFRA / "variables.tf").read_text()
    consumers = _block(variables, 'variable "vault_openviking_consumers" {')
    assert "veerle" not in consumers


CUTOVER_STEPS = [
    "nomad job stop openviking",
    "Record a baseline",
    "Apply `deployments/infrastructure`",
    "CREATE SCHEMA IF NOT EXISTS openviking_v2",
    "Apply `deployments/applications`",
    "nomad job restart hermes",
]


def test_cutover_steps_are_documented() -> None:
    readme = README.read_text()
    positions = []
    for step in CUTOVER_STEPS:
        at = readme.find(step)
        assert at != -1, f"the README never says `{step}`"
        positions.append(at)
    assert positions == sorted(positions), (
        f"the cutover steps are out of order; want {CUTOVER_STEPS}"
    )
