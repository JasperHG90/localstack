"""Drift tests: the buckets the nightly MinIO backup names are real buckets.

`rclone sync` against a bucket that does not exist does not loudly fail a
periodic batch job, so a typo in the jobspec buys a silently empty backup that
nobody notices until a restore. These tests pin the names in the jobspec to the
bucket set `deployments/applications/storage.tf` declares, and pin each GCS
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

# The durable buckets. loki and tempo keep 30 days and are left out on purpose.
EXPECTED_BUCKETS = {"openviking", "registry", "models", "datalake"}

SYNC_LINE = re.compile(
    r"^\s*rclone sync seaweedfs:(\S+) gcs:\$\{gcs_bucket\}/minio/([^/\s]+)/ .*$", re.M
)


def _require(value: str | None, what: str) -> str:
    """Self-check: a None from the parser cannot pass vacuously."""
    if not value:
        pytest.fail(f"parser found no {what} — the jobspec cannot be checked")
    return value


def _sync_lines() -> list[re.Match[str]]:
    """Every `rclone sync seaweedfs:<bucket> gcs:${gcs_bucket}/minio/<bucket>/` line."""
    lines = list(SYNC_LINE.finditer(JOBSPEC.read_text()))
    if not lines:
        pytest.fail("parser found no rclone sync line in backup-minio.hcl — it cannot be checked")
    return lines


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


def test_minio_backup_syncs_declared_buckets() -> None:
    declared = _declared_buckets()
    for line in _sync_lines():
        bucket = line.group(1)
        assert bucket in declared, (
            f"backup-minio.hcl syncs `seaweedfs:{bucket}`, which is not a bucket declared in "
            f"deployments/applications/storage.tf (declared: {sorted(declared)}). "
            "rclone sync against a nonexistent bucket backs up nothing, quietly."
        )


def test_every_rclone_transfer_is_a_checked_sync_line() -> None:
    """A transfer written in another shape would escape every check in this file."""
    transfers = re.findall(r"\brclone (?:sync|copy|move)\b", JOBSPEC.read_text())
    assert len(transfers) == len(_sync_lines()), (
        f"backup-minio.hcl runs {len(transfers)} rclone transfers but only "
        f"{len(_sync_lines())} match the shape the coverage checks read"
    )


def test_minio_backup_syncs_the_durable_buckets() -> None:
    sources = [line.group(1) for line in _sync_lines()]
    assert sorted(sources) == sorted(EXPECTED_BUCKETS), (
        f"backup-minio.hcl syncs {sorted(sources)}, expected {sorted(EXPECTED_BUCKETS)}, each once."
    )
    for line in _sync_lines():
        source, destination = line.group(1), line.group(2)
        assert destination == source, (
            f"backup-minio.hcl reads bucket `{source}` but writes to the "
            f"`minio/{destination}/` prefix in GCS. Source and destination must name "
            "the same bucket, or the backup lands under the wrong path."
        )


def test_minio_backup_keeps_directory_markers() -> None:
    """OpenViking's empty directories are zero-byte `/` keys that rclone skips by default.

    Losing them does not fail `rclone check`, so only the flags guard them.
    """
    for line in _sync_lines():
        for flag in ("--create-empty-src-dirs", "--gcs-directory-markers"):
            assert flag in line.group(0), f"`{line.group(0).strip()}` lacks {flag}"


def test_minio_backup_fails_when_any_sync_fails() -> None:
    """Every sync runs, and any one failing makes the task exit nonzero.

    `&&` would skip the later buckets after one failure, and `;` alone would
    exit 0 on a failed sync, so a periodic job would report a green run.
    """
    text = JOBSPEC.read_text()
    for line in _sync_lines():
        assert line.group(0).rstrip().endswith("|| rc=1"), (
            f"`{line.group(0).strip()}` does not record its failure with `|| rc=1`."
        )
    assert re.search(r"^\s*rc=0\s*$", text, re.M), "the script never sets rc=0 before the syncs"
    assert re.search(r"^\s*exit \$rc\s*$", text, re.M), "the script never ends with `exit $rc`"


# -- Doc drift: docs/reference/gcs-backups.md against the jobspecs -------------
#
# Four claims in that page have already gone stale under commits that moved
# the code and left the prose alone: both node constraints and two CPU figures.
# These tests pin every fact the document states that a parser can also read
# out of the source, so the next such commit reddens instead of rotting.

DOC = REPO_ROOT / "docs" / "reference" / "gcs-backups.md"
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
        f"docs/reference/gcs-backups.md says the Google provider is {doc_version}, "
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
            f"docs/reference/gcs-backups.md never names."
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
                "bullet for that task in docs/reference/gcs-backups.md does not state."
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
            "docs/reference/gcs-backups.md does not state literally."
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
                "task in docs/reference/gcs-backups.md does not name."
            )


def test_backup_reads_seaweedfs_with_its_read_only_key() -> None:
    """Since the cutover the source is SeaweedFS, through the backup user's key."""
    jobspec = JOBSPEC.read_text()
    assert "[seaweedfs]\ntype = s3\nprovider = SeaweedFS\n" in jobspec
    assert "endpoint = http://${seaweedfs_host}:8333" in jobspec
    assert "[minio]" not in jobspec and "minio:" not in jobspec.replace("/minio/", "")
    services = (REPO_ROOT / "deployments" / "infrastructure" / "services.tf").read_text()
    job = re.search(r'resource "nomad_job" "backup_minio" \{(.*?)\n\}', services, re.S)
    assert job, 'services.tf has no resource "nomad_job" "backup_minio"'
    assert '"${vault_mount.kvv2.path}/data/default/backup-minio/seaweedfs"' in job.group(1)
