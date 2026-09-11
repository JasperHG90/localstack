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


# -- Doc drift: docs/gcs-backups.md against the jobspecs -----------------------
#
# Four claims in that runbook have already gone stale under commits that moved
# the code and left the prose alone: both node constraints and two CPU figures.
# These tests pin every fact the document states that a parser can also read
# out of the source, so the next such commit reddens instead of rotting.

DOC = REPO_ROOT / "docs" / "gcs-backups.md"
PROVIDERS = REPO_ROOT / "deployments" / "infrastructure" / "providers.tf"
PG_JOBSPEC = REPO_ROOT / "deployments" / "infrastructure" / "services" / "backup-postgres.hcl"

JOBSPECS = {"backup-postgres.hcl": PG_JOBSPEC, "backup-minio.hcl": JOBSPEC}


def _doc_section(jobspec_name: str) -> str:
    """The doc block describing one jobspec, heading to the next heading.

    Stops at `###` as well as `##`. Stopping only at `##` would run the
    postgres section on through the minio one, and each job would then be
    checked against the other's node, images and figures.
    """
    text = DOC.read_text()
    start = text.find(f"### `deployments/infrastructure/services/{jobspec_name}`")
    if start == -1:
        pytest.fail(f"no doc section for {jobspec_name} — the doc cannot be checked")
    nxt = re.search(r"\n#{2,3} ", text[start + 1 :])
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def _hcl_blocks(path: Path, keyword: str) -> dict[str, str]:
    """Bodies of `resources {` or `config {` blocks, keyed by the owning task.

    Brace counting, not a flat regex: `resources` figures must bind to the task
    that owns them, or swapping two tasks' numbers would still pass.
    """
    text = path.read_text()
    blocks: dict[str, str] = {}
    task: str | None = None
    owner = ""
    body: list[str] = []
    depth = 0
    for line in text.splitlines():
        match = re.match(r'\s*task\s+"([^"]+)"\s*\{', line)
        if match:
            task = match.group(1)
        if task and not depth and re.match(rf"\s*{keyword}\s*\{{", line):
            owner = task
            body = []
            depth = 1
            continue
        if depth:
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                blocks[owner] = "\n".join(body)
                depth = 0
                continue
            body.append(line)
    return blocks


def _doc_task_block(section: str, task: str) -> str:
    """The part of a doc section describing one task, its bullet to the next.

    Without this the doc side is plain membership in the whole section, so
    swapping two same-section tasks' figures still passes. `pgdump` and
    `upload` are exactly that pair, and exactly the pair that drifted before.
    """
    start = re.search(rf"^- \*\*[^*]+\*\* \(`{re.escape(task)}`\)", section, re.M)
    if not start:
        pytest.fail(f"doc section names no task `{task}` — it cannot be checked")
    rest = section[start.end() :]
    nxt = re.search(r"^- \*\*", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def test_backup_doc_names_the_google_provider_version() -> None:
    doc = re.search(r"`hashicorp/google\s+(~>[\d.]+)`", DOC.read_text())
    declared = re.search(
        r'google\s*=\s*\{[^}]*?version\s*=\s*"([^"]+)"', PROVIDERS.read_text(), re.S
    )
    doc_version = _require(doc.group(1) if doc else None, "provider version in the doc")
    src_version = _require(
        declared.group(1) if declared else None, "google version in providers.tf"
    )
    assert doc_version == src_version, (
        f"docs/gcs-backups.md says the Google provider is {doc_version}, "
        f"providers.tf declares {src_version}."
    )


def test_backup_doc_matches_jobspec_node_constraints() -> None:
    for name, path in JOBSPECS.items():
        # Not a `[^}]*` span: the constraint's own `attribute` value contains
        # `${attr.unique.hostname}`, whose brace ends the span early.
        src = re.search(
            r"constraint\s*\{(?:[^{}]|\{[^{}]*\})*?"  # inside one constraint block
            r'value\s*=\s*"([^"]+)"',
            path.read_text(),
        )
        node = _require(src.group(1) if src else None, f"constraint in {name}")
        section = _doc_section(name)
        doc_nodes = re.findall(r"`([a-z0-9-]+)`", section)
        assert node in doc_nodes, (
            f"{name} is constrained to `{node}`, which its section of "
            f"docs/gcs-backups.md never names."
        )


def test_backup_doc_matches_jobspec_resources() -> None:
    for name, path in JOBSPECS.items():
        blocks = _hcl_blocks(path, "resources")
        if not blocks:
            pytest.fail(f"parsed no resources blocks from {name}")
        section = _doc_section(name)
        for task, body in blocks.items():
            cpu = _require(
                (m := re.search(r"cpu\s*=\s*(\d+)", body)) and m.group(1),
                f"cpu for task {task} in {name}",
            )
            memory = _require(
                (m := re.search(r"memory\s*=\s*(\d+)", body)) and m.group(1),
                f"memory for task {task} in {name}",
            )
            assert f"{cpu} MHz CPU, {memory} MB memory" in _doc_task_block(section, task), (
                f"{name} task `{task}` sets {cpu} MHz / {memory} MB, which the "
                "bullet for that task in docs/gcs-backups.md does not state."
            )


def test_backup_doc_matches_jobspec_schedules_and_images() -> None:
    for name, path in JOBSPECS.items():
        text = path.read_text()
        section = _doc_section(name)

        cron = _require(
            (m := re.search(r'crons\s*=\s*\["([^"]+)"\]', text)) and m.group(1),
            f"cron in {name}",
        )
        assert f"`{cron}`" in section, (
            f"{name} runs on cron `{cron}`, which its section of "
            "docs/gcs-backups.md does not state literally."
        )

        configs = _hcl_blocks(path, "config")
        if not configs:
            pytest.fail(f"parsed no config blocks from {name}")
        for task, body in configs.items():
            image = _require(
                (m := re.search(r'image\s*=\s*"([^"]+)"', body)) and m.group(1),
                f"image for task {task} in {name}",
            )
            assert f"`{image}`" in _doc_task_block(section, task), (
                f"{name} task `{task}` runs `{image}`, which the bullet for that "
                "task in docs/gcs-backups.md does not name."
            )
