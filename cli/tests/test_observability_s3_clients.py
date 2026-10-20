"""Drift tests: Loki and Tempo log in to SeaweedFS keylessly, and Grafana
watches SeaweedFS.

Each client fails quietly when one setting goes missing: without
`AWS_ROLE_ARN`, Tempo's minio-go falls back to anonymous S3 with no error,
and without `RoleArn` and `RoleSessionName`, SeaweedFS refuses loki's
exchange (spike:seaweedfs-workload-identity/3).
"""

import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SERVICES = REPO_ROOT / "deployments" / "applications" / "services"
GRAFANA = REPO_ROOT / "deployments" / "infrastructure" / "services" / "grafana"
LOKI = APP_SERVICES / "loki.hcl"
TEMPO = APP_SERVICES / "tempo.hcl"


def _identity(jobspec: str) -> str:
    block = re.search(r"identity \{(.*?)\}", jobspec, re.S)
    if not block:
        pytest.fail("jobspec has no identity block")
    return block.group(1)


@pytest.mark.parametrize("jobspec", [LOKI, TEMPO], ids=["loki", "tempo"])
def test_identity_is_for_seaweedfs(jobspec: Path) -> None:
    identity = _identity(jobspec.read_text())
    assert re.search(r'aud\s*=\s*\["seaweedfs"\]', identity)
    assert 'filepath    = "secrets/nomad_seaweedfs.jwt"' in identity


@pytest.mark.parametrize("jobspec", [LOKI, TEMPO], ids=["loki", "tempo"])
def test_no_hardcoded_old_store_endpoint(jobspec: Path) -> None:
    text = jobspec.read_text()
    assert "192.168.2.29:9000" not in text
    assert "${s3_host}:8333" in text


def test_loki_helper_names_its_role_and_session() -> None:
    text = LOKI.read_text()
    url = re.search(r'"http://\$\{s3_host\}:8333/\?Action=AssumeRoleWithWebIdentity[^"]*"', text)
    assert url, "loki's credential helper does not call SeaweedFS's STS"
    assert "RoleArn=arn:aws:iam::role/loki" in url.group(0)
    assert "RoleSessionName=loki" in url.group(0)
    assert "cat /secrets/nomad_seaweedfs.jwt" in text


def test_tempo_sets_its_role_arn() -> None:
    text = TEMPO.read_text()
    assert re.search(r'AWS_ROLE_ARN\s*=\s*"arn:aws:iam::role/tempo"', text)
    assert re.search(r'AWS_WEB_IDENTITY_TOKEN_FILE\s*=\s*"/secrets/nomad_seaweedfs\.jwt"', text)
    assert re.search(r'TEST_IAM_ENDPOINT\s*=\s*"http://\$\{s3_host\}:8333"', text)


def test_scrape_job_missing_watches_seaweedfs() -> None:
    rules = (GRAFANA / "alert-rules.yaml").read_text()
    expr = re.search(r"expr: '(absent\(up\{job=\"node\"\}\).*?)'", rules)
    assert expr, "alert-rules.yaml has no ScrapeJobMissing expression"
    assert 'absent(up{job="seaweedfs"})' in expr.group(1)


def test_seaweedfs_dashboard_and_alerts_are_provisioned() -> None:
    rules = (GRAFANA / "alert-rules.yaml").read_text()
    for uid in ("alert-seaweedfs-down", "alert-seaweedfs-disk-error"):
        assert f"uid: {uid}" in rules
    assert (GRAFANA / "seaweedfs.json").exists()
    grafana = (GRAFANA.parent / "grafana.hcl").read_text()
    assert 'destination = "local/dashboards/seaweedfs.json"' in grafana
