"""Drift tests: the restore job keeps what makes a restore complete, and
OpenViking reads SeaweedFS.

`rclone check` passes with every directory marker missing
(spike:seaweedfs-cutover-openviking/2), so the marker flags and the one-way
directory listing are what stand between a restore and an OpenViking tree
that quietly lost its empty directories.
"""

import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "deployments" / "infrastructure"
APPS = REPO_ROOT / "deployments" / "applications"
RESTORE = INFRA / "services" / "restore-s3.hcl"
DURABLE_BUCKETS = {"openviking", "openviking-v2", "registry", "models", "datalake"}


@pytest.fixture(scope="module")
def restore() -> str:
    return RESTORE.read_text()


def _line(script: str, command: str) -> str:
    matches = [line for line in script.splitlines() if line.strip().startswith(command)]
    if len(matches) != 1:
        pytest.fail(f"restore-s3.hcl has {len(matches)} lines starting with `{command}`, want 1")
    return matches[0]


def test_restore_is_a_parameterized_job_taking_a_bucket(restore: str) -> None:
    assert re.search(r'parameterized\s*\{\s*meta_required\s*=\s*\["bucket"\]', restore)
    assert 'b="$NOMAD_META_bucket"' in restore


def test_copy_keeps_directory_markers_on_both_sides(restore: str) -> None:
    copy = _line(restore, 'rclone copy "$src" "$dst"')
    for flag in ("--create-empty-src-dirs", "--gcs-directory-markers", "--s3-directory-markers"):
        assert flag in copy, f"the restore copy drops {flag}"
    assert copy.rstrip().endswith("|| exit 1")


def test_check_fails_the_run(restore: str) -> None:
    assert _line(restore, 'rclone check "$src" "$dst"').rstrip().endswith("|| exit 2")


def test_every_gcs_directory_must_exist_on_seaweedfs(restore: str) -> None:
    src = _line(restore, 'rclone lsf -R --dirs-only --gcs-directory-markers "$src"')
    dst = _line(restore, 'rclone lsf -R --dirs-only --s3-directory-markers "$dst"')
    assert "> /tmp/src-dirs" in src and "> /tmp/dst-dirs" in dst
    assert "missing=$(comm -23 /tmp/src-dirs /tmp/dst-dirs)" in restore
    assert re.search(r'if \[ -n "\$missing" \]; then.*?exit 3\s*fi', restore, re.S), (
        "a directory missing on SeaweedFS does not fail the run"
    )


def test_restore_reads_its_own_keys() -> None:
    services = (INFRA / "services.tf").read_text()
    job = re.search(r'resource "nomad_job" "restore_s3" \{(.*?)\n\}', services, re.S)
    assert job, 'services.tf has no resource "nomad_job" "restore_s3"'
    assert '"${vault_mount.kvv2.path}/data/default/restore-s3/seaweedfs"' in job.group(1)
    assert "vault_kv_secret_v2.restore_s3_gcs_credentials.path" in job.group(1)
    secrets = (INFRA / "secrets.tf").read_text()
    assert re.search(
        r'"restore_s3_gcs_credentials" \{[^}]*name\s*=\s*"default/restore-s3/gcs"', secrets
    )
    app_secrets = (APPS / "secrets.tf").read_text()
    assert re.search(
        r'"restore_seaweedfs_credentials" \{[^}]*name\s*=\s*"default/restore-s3/seaweedfs"',
        app_secrets,
    )


def test_restore_user_writes_only_the_durable_buckets() -> None:
    storage = (APPS / "storage.tf").read_text()
    policy = re.search(
        r'resource "aws_iam_user_policy" "seaweedfs_restore" \{(.*?)\n\}', storage, re.S
    )
    assert policy, 'storage.tf has no resource "aws_iam_user_policy" "seaweedfs_restore"'
    assert "Action = local.seaweedfs_write_actions" in policy.group(1)
    assert "for b in local.seaweedfs_durable_buckets" in policy.group(1)
    durable = re.search(r"seaweedfs_durable_buckets\s*=\s*\[([^\]]*)\]", storage)
    assert durable and set(re.findall(r'"([^"]+)"', durable.group(1))) == DURABLE_BUCKETS


def test_openviking_reads_seaweedfs() -> None:
    conf = (APPS / "services" / "openviking" / "ov.conf.json").read_text()
    assert '"endpoint": "${s3_endpoint}"' in conf
    assert "{{ $s3.Data.data.access_key }}" in conf and "$minio" not in conf
    jobspec = (APPS / "services" / "openviking.hcl").read_text()
    assert '{{- $s3 := secret "${openviking_s3_secret}" -}}' in jobspec
    services = (APPS / "services.tf").read_text()
    assert (
        'openviking_s3_secret      = vault_kv_secret_v2.seaweedfs_credentials["openviking"].path'
        in services
    )
    assert re.search(
        r's3_endpoint\s*=\s*"http://\$\{data\.consul_service\.seaweedfs\.service\[0\]\.node_address\}:8333"',
        services,
    )
    assert "openviking_minio_secret" not in services


def test_no_rclone_output_is_piped(restore: str) -> None:
    """Without pipefail a pipe takes its last command's status: a failed listing would pass."""
    single_pipe = re.compile(r"\brclone\b[^#]*(?<!\|)\|(?!\|)")
    piped = [line.strip() for line in restore.splitlines() if single_pipe.search(line)]
    assert piped == [], f"rclone output piped into another command: {piped}"


def test_only_durable_buckets_are_restored(restore: str) -> None:
    """A typo must not exit 0 as 'nothing to restore'."""
    case = re.search(r'case "\$b" in\s*\n\s*([a-z0-9|-]+)\) ;;\s*\n\s*\*\).*?exit 5', restore)
    assert case, "restore-s3.hcl does not refuse a bucket outside the allowlist with exit 5"
    assert set(case.group(1).split("|")) == DURABLE_BUCKETS
