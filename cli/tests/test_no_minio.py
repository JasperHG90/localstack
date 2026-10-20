"""MinIO is gone from the code: only the names that outlive it on purpose remain.

Each allowed name has a reason that is not "MinIO still runs":
- `minio/` is the GCS prefix the backup has always written, kept so the
  history carries on; the restore job reads the same prefix.
- `minio_data` is the old store's host volume. Its data stays until the
  operator promotes the `minio-volume-destroy` ticket.
- `minio-go` is the Go S3 client library Tempo is built on.
- `minio/mc` is the S3 client the devcontainer installs, which works against
  SeaweedFS.
- `alert-minio-degraded` is listed under Grafana's `deleteRules`, which is how
  a provisioned rule that left the file gets deleted.
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED = [
    REPO_ROOT / "deployments",
    REPO_ROOT / "bootstrap",
    REPO_ROOT / "cli" / "src",
    REPO_ROOT / ".devcontainer" / "Dockerfile",
]
SKIPPED_PARTS = {".terraform", "__pycache__", ".venv", "node_modules"}
ALLOWED = [
    (re.compile(r"\bminio/"), {"backup-s3.hcl", "restore-s3.hcl"}),
    (re.compile(r"minio_data"), {"services.tf"}),
    (re.compile(r"minio-go"), {"tempo.hcl"}),
    (re.compile(r"uid: alert-minio-degraded"), {"alert-rules.yaml"}),
    (re.compile(r"github\.com/minio/mc/|MinIO retired that host"), {"Dockerfile"}),
]


def _files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and not SKIPPED_PARTS & set(path.parts):
                files.append(path)
    return files


def _unexplained(path: Path, line: str) -> bool:
    for pattern, names in ALLOWED:
        if path.name in names:
            line = pattern.sub("", line)
    return "minio" in line.lower()


def test_no_minio_outside_the_names_that_outlive_it() -> None:
    offenders = []
    for path in _files():
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if "minio" in line.lower() and _unexplained(path, line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()[:100]}")
    assert offenders == [], "MinIO is still named in:\n" + "\n".join(offenders)


def test_the_scan_sees_the_kept_prefix() -> None:
    """Guard against a scan that silently reads nothing."""
    backup = REPO_ROOT / "deployments" / "infrastructure" / "services" / "backup-s3.hcl"
    assert backup in _files()
    assert "/minio/" in backup.read_text()
