"""Drift tests: the bucket the nightly MinIO backup names is a real bucket.

`rclone sync` against a bucket that does not exist does not loudly fail a
periodic batch job, so a typo in the jobspec buys a silently empty backup that
nobody notices until a restore. These tests pin the name in the jobspec to the
bucket set `deployments/applications/storage.tf` declares, and pin the GCS
destination prefix to the same name so the two cannot drift apart.

Each parser carries a self-check, so a parser that finds nothing fails rather
than passing vacuously.
"""

import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
JOBSPEC = REPO_ROOT / "deployments" / "infrastructure" / "services" / "backup-minio.hcl"
APP_STORAGE = REPO_ROOT / "deployments" / "applications" / "storage.tf"

EXPECTED_BUCKET = "openviking"


def _require(value: str | None, what: str) -> str:
    """Self-check: a None from the parser cannot pass vacuously."""
    if not value:
        pytest.fail(f"parser found no {what} — the jobspec cannot be checked")
    return value


def _sync_source_bucket() -> str:
    """The bucket in `rclone sync minio:<bucket> ...`."""
    match = re.search(r"rclone sync minio:(\S+)", JOBSPEC.read_text())
    return _require(match.group(1) if match else None, "rclone sync source in backup-minio.hcl")


def _sync_destination_bucket() -> str:
    """The bucket segment of the `gcs:<gcs_bucket>/minio/<bucket>/` destination."""
    match = re.search(r"gcs:\$\{gcs_bucket\}/minio/([^/\s]+)/", JOBSPEC.read_text())
    return _require(match.group(1) if match else None, "GCS destination prefix in backup-minio.hcl")


def _declared_buckets() -> set[str]:
    """The keys of `local.buckets` in the applications root.

    Parsed from the `buckets = {` block by brace depth rather than by a flat
    regex over the file: `storage.tf` also declares policies and modules whose
    keys would otherwise read as bucket names.
    """
    text = APP_STORAGE.read_text()
    start = text.find("buckets = {")
    if start == -1:
        pytest.fail("no `buckets = {` block in deployments/applications/storage.tf")
    depth = 0
    names: set[str] = set()
    for line in text[start:].splitlines():
        if depth == 1:
            key = re.match(r'\s*"?([A-Za-z0-9_-]+)"?\s*=\s*\{', line)
            if key:
                names.add(key.group(1))
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
    if not names:
        pytest.fail("parsed no bucket names from `local.buckets` — the check is vacuous")
    return names


def test_minio_backup_syncs_a_declared_bucket() -> None:
    bucket = _sync_source_bucket()
    declared = _declared_buckets()
    assert bucket in declared, (
        f"backup-minio.hcl syncs `minio:{bucket}`, which is not a bucket declared in "
        f"deployments/applications/storage.tf (declared: {sorted(declared)}). "
        "rclone sync against a nonexistent bucket backs up nothing, quietly."
    )


def test_minio_backup_syncs_the_openviking_bucket() -> None:
    source = _sync_source_bucket()
    destination = _sync_destination_bucket()
    assert source == EXPECTED_BUCKET, (
        f"backup-minio.hcl syncs `{source}`, expected `{EXPECTED_BUCKET}`."
    )
    assert destination == source, (
        f"backup-minio.hcl reads bucket `{source}` but writes to the "
        f"`minio/{destination}/` prefix in GCS. Source and destination must name "
        "the same bucket, or the backup lands under the wrong path."
    )
