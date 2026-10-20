"""Drift tests: the SeaweedFS jobspec keeps the settings its spikes proved.

Each setting below fixed a failure measured in a spike, and each one fails
quietly when dropped: a missing growth override only shows when the fifth
bucket takes its first write, and a dropped loopback bind exposes the filer's
unauthenticated IAM gRPC to the LAN with nothing else changing.
"""

import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
JOBSPEC = REPO_ROOT / "deployments" / "infrastructure" / "services" / "seaweedfs.hcl"

# CVE-2026-77298: the OIDC bearer path skipped the role trust policy before 4.40.
MIN_VERSION = (4, 40)

REQUIRED_FLAGS = [
    "-ip=127.0.0.1",
    "-ip.bind=127.0.0.1",
    "-s3.ip.bind=0.0.0.0",
    "-metricsIp=0.0.0.0",
    "-s3.iam.readOnly=false",
    "-volume.max=0",
    "-master.volumeSizeLimitMB=1024",
    "-master.volumePreallocate=false",
]


@pytest.fixture(scope="module")
def jobspec() -> str:
    return JOBSPEC.read_text()


def test_image_is_pinned_at_or_above_the_cve_fix(jobspec: str) -> None:
    match = re.search(r'image\s*=\s*"docker\.io/chrislusf/seaweedfs:(\d+)\.(\d+)"', jobspec)
    assert match, "seaweedfs.hcl pins no exact chrislusf/seaweedfs:<major>.<minor> image"
    assert (int(match.group(1)), int(match.group(2))) >= MIN_VERSION, (
        f"image {match.group(1)}.{match.group(2)} predates the CVE-2026-77298 fix in 4.40"
    )


@pytest.mark.parametrize("flag", REQUIRED_FLAGS)
def test_server_flag_is_set(jobspec: str, flag: str) -> None:
    assert f'"{flag}"' in jobspec, f"weed server is started without {flag}"


def test_master_grows_two_volumes_per_collection(jobspec: str) -> None:
    """The default `copy_1 = 7` filled every slot after four buckets."""
    assert re.search(r"\[master\.volume_growth\]\s*\n\s*copy_1\s*=\s*2\b", jobspec), (
        "master.toml does not set [master.volume_growth] copy_1 = 2"
    )


def test_master_toml_is_mounted_where_weed_reads_it(jobspec: str) -> None:
    """A rendered master.toml that is not mounted leaves the default growth in force."""
    assert re.search(r'destination\s*=\s*"local/master\.toml"', jobspec), (
        "master.toml is not rendered to local/"
    )
    assert '"local/master.toml:/etc/seaweedfs/master.toml"' in jobspec, (
        "local/master.toml is not mounted at /etc/seaweedfs/master.toml, "
        "so weed never reads copy_1 = 2"
    )


def test_only_s3_and_metrics_ports_are_mapped(jobspec: str) -> None:
    network = re.search(r"network\s*\{(.*?)\n    \}", jobspec, re.S)
    assert network, "seaweedfs.hcl has no group network block"
    labels = re.findall(r'port\s+"([^"]+)"', network.group(1))
    assert sorted(labels) == ["metrics", "s3"], (
        f"seaweedfs.hcl maps ports {labels}; only s3 and metrics may leave the host"
    )


def test_service_carries_the_s3_tag(jobspec: str) -> None:
    """The CLI's `s3` route resolves to the one service with that tag, SeaweedFS."""
    tags = re.findall(r"tags\s*=\s*\[([^\]]*)\]", jobspec)
    assert any('"s3"' in t for t in tags), "the seaweedfs service lost the s3 tag"
    minio = (JOBSPEC.parent / "minio.hcl").read_text()
    for minio_tags in re.findall(r"tags\s*=\s*\[([^\]]*)\]", minio):
        assert '"s3"' not in minio_tags, (
            "minio still carries the s3 tag, so the route has two carriers"
        )
