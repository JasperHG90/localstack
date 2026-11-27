"""Drift tests: OpenViking's base image and the extension pins move together.

ov-postgres v0.7.0 and ov-ext v0.8.0 refuse an OpenViking outside >=0.5.6,<0.6
at startup, and the Dockerfile installs them with --no-deps, so a base image
that moved without its pins, or pins that moved without the base, fails only
on the node (spike:openviking-update-0-5/2).
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"
DOCKERFILE = APPS / "services" / "openviking" / "Dockerfile.openviking"


def _pin(name: str) -> list[str]:
    return re.findall(rf'^\s*{name}\s*=\s*"([^"]+)"', (APPS / "services.tf").read_text(), re.M)


def test_images_are_pinned_to_0_5_6() -> None:
    assert _pin("openviking_base_image") == ["ghcr.io/volcengine/openviking:v0.5.6"]
    assert _pin("openviking_image") == ["ghcr.io/jasperhg90/openviking:v0.5.6-1"]


def test_extensions_are_pinned_to_their_0_5_6_tags() -> None:
    tags = re.findall(r"openviking_extensions@([^#\"]+)#", DOCKERFILE.read_text())
    assert sorted(tags) == ["ov-ext-v0.8.0", "ov-postgres-v0.7.0"]
