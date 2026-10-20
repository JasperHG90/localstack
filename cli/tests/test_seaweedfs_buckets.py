"""Drift tests: SeaweedFS keeps its catalog of buckets, users and grants.

`deployments/applications/storage.tf` derives every SeaweedFS bucket and user
from `local.buckets`, so these tests read the few literals that steer the
derivation: which buckets exist, which actions a writer, a reader and the
backup user get, and which buckets the backup user reaches.
"""

import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
STORAGE = REPO_ROOT / "deployments" / "applications" / "storage.tf"

SEAWEEDFS_BUCKETS = {"datalake", "models", "registry", "openviking", "loki", "tempo"}
DURABLE_BUCKETS = {"openviking", "registry", "models", "datalake"}
WRITE_ACTION = re.compile(r"s3:(\*|Put|Delete|Create|Abort|Restore|Replicate)")


@pytest.fixture(scope="module")
def storage() -> str:
    return STORAGE.read_text()


def _list(storage: str, name: str) -> list[str]:
    match = re.search(rf"^\s*{name}\s*=\s*\[([^\]]*)\]", storage, re.M)
    if not match:
        pytest.fail(f"storage.tf has no `{name} = [...]` local")
    return re.findall(r'"([^"]+)"', match.group(1))


def _catalog_buckets(storage: str) -> set[str]:
    start = storage.find("buckets = {")
    depth = 0
    names: set[str] = set()
    for line in storage[start:].splitlines():
        if depth == 1:
            key = re.match(r'\s*"?([A-Za-z0-9_-]+)"?\s*=\s*\{', line)
            if key:
                names.add(key.group(1))
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
    if not names:
        pytest.fail("parsed no bucket names from `local.buckets`")
    return names


def _resource(storage: str, kind: str, name: str) -> str:
    match = re.search(rf'^resource "{kind}" "{name}" \{{\n(.*?)^\}}', storage, re.M | re.S)
    if not match:
        pytest.fail(f'storage.tf has no resource "{kind}" "{name}"')
    return match.group(1)


def test_seaweedfs_gets_exactly_the_six_buckets(storage: str) -> None:
    assert _catalog_buckets(storage) == SEAWEEDFS_BUCKETS
    assert "seaweedfs_buckets = local.buckets" in storage


@pytest.mark.parametrize(
    ("kind", "name", "source"),
    [
        ("aws_s3_bucket", "seaweedfs", "local.seaweedfs_buckets"),
        ("aws_iam_user", "seaweedfs", "local.seaweedfs_users"),
        ("aws_iam_access_key", "seaweedfs", "local.seaweedfs_users"),
        ("aws_iam_user_policy", "seaweedfs", "local.seaweedfs_users"),
    ],
)
def test_resources_follow_the_derived_locals(
    storage: str, kind: str, name: str, source: str
) -> None:
    assert f"for_each = {source}" in _resource(storage, kind, name)


def test_users_keep_their_reader_writer_split(storage: str) -> None:
    """Writers get the write actions and readers the read actions, per bucket."""
    users = re.search(r"seaweedfs_users = merge\(\[(.*?)\]\.\.\.\)", storage, re.S)
    assert users, "storage.tf has no seaweedfs_users local"
    body = users.group(1)
    assert "for name, bucket in local.seaweedfs_buckets" in body
    assert re.search(
        r"for w in bucket\.writers : w\.name => \{[^}]*local\.seaweedfs_write_actions", body
    )
    assert re.search(
        r"for r in bucket\.readers : r\.name => \{[^}]*local\.seaweedfs_read_actions", body
    )


# The grants carried over from the previous store: writers get every action on
# their bucket, readers can get an object but not list.
EXPECTED_ACTIONS = {
    "seaweedfs_write_actions": ["s3:*"],
    "seaweedfs_read_actions": ["s3:GetBucketLocation", "s3:GetObject"],
}


@pytest.mark.parametrize("local", sorted(EXPECTED_ACTIONS))
def test_actions_keep_their_grants(storage: str, local: str) -> None:
    assert sorted(_list(storage, local)) == sorted(EXPECTED_ACTIONS[local])


def test_backup_actions_are_read_plus_list(storage: str) -> None:
    """rclone lists to sync, so the backup user alone adds s3:ListBucket."""
    match = re.search(r"^\s*seaweedfs_backup_actions\s*=\s*(.+)$", storage, re.M)
    assert match, "storage.tf has no seaweedfs_backup_actions local"
    assert match.group(1).strip() == 'concat(local.seaweedfs_read_actions, ["s3:ListBucket"])'
    assert not [a for a in _list(storage, "seaweedfs_read_actions") if WRITE_ACTION.match(a)]


def test_backup_user_reads_only_the_durable_buckets(storage: str) -> None:
    assert set(_list(storage, "seaweedfs_durable_buckets")) == DURABLE_BUCKETS
    policy = _resource(storage, "aws_iam_user_policy", "seaweedfs_backup")
    assert "Action = local.seaweedfs_backup_actions" in policy, (
        "backup policy is not the read-only action set"
    )
    assert "for b in local.seaweedfs_durable_buckets" in policy, (
        "backup policy reaches other buckets"
    )
