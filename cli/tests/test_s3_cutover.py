"""Drift tests: everything that names "the S3 store" points at SeaweedFS.

The `s3` Consul tag, the `s3.lab` edge route, the dash tile and the
devcontainer's `mc` alias each pointed at MinIO before the cutover. Any one
left behind sends a client to a store nothing writes to any more.
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENTS = REPO_ROOT / "deployments"
HAPROXY = DEPLOYMENTS / "infrastructure" / "services" / "haproxy.hcl"
TILES = DEPLOYMENTS / "applications" / "services" / "dash" / "tiles.json"
OLD_STORE_ADDRESS = "192.168.2.29:9000"


def _backend(name: str) -> str:
    block = re.search(rf"^backend {name}\n((?:    .*\n)+)", HAPROXY.read_text(), re.M)
    assert block, f"haproxy.hcl has no backend {name}"
    return block.group(1)


def test_s3_route_points_at_seaweedfs() -> None:
    assert "server s3_1 192.168.2.29:8333 check" in _backend("s3")


def test_old_console_route_is_gone() -> None:
    assert "backend minio" not in HAPROXY.read_text()
    assert "192.168.2.29:9001" not in HAPROXY.read_text()


def test_dash_tile_is_seaweedfs() -> None:
    tiles = TILES.read_text()
    assert '"key": "seaweedfs"' in tiles
    assert '"key": "minio"' not in tiles
    assert "MinIO bucket" not in tiles


def test_devcontainer_alias_and_example_name_seaweedfs() -> None:
    bootstrap = (REPO_ROOT / ".devcontainer" / "bootstrap.sh").read_text()
    assert 'mc alias set s3 "${AWS_ENDPOINT_URL_S3}"' in bootstrap
    example = (REPO_ROOT / ".devcontainer" / ".env.example").read_text()
    assert "AWS_ENDPOINT_URL_S3=https://s3.lab.orangecluster.nl" in example
    assert "secret/default/seaweedfs/admin" in example
    assert "MINIO_" not in example


def test_no_jobspec_names_the_old_store_address() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in DEPLOYMENTS.rglob("*.hcl")
        if OLD_STORE_ADDRESS in path.read_text()
    ]
    assert offenders == [], f"jobspecs still naming the old store's address: {offenders}"
