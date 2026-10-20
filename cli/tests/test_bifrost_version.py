"""Drift tests: Bifrost's pin, its provider and the smoke script move together.

The 2.1.0 to 2.3.1 store migrations cannot be undone, and 2.1.0 renamed the
unknown-key refusal, so a pin that moved without the smoke script would fail
its own check (spike:bifrost-update/1, /3, /4).
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"


def test_bifrost_is_pinned_to_2_3_1() -> None:
    pins = re.findall(r'bifrost_version\s*=\s*"([^"]+)"', (APPS / "services.tf").read_text())
    assert pins == ["2.3.1"]


def test_provider_stays_on_0_1() -> None:
    block = re.search(r"bifrost = \{(.*?)\}", (APPS / "providers.tf").read_text(), re.S)
    assert block, "providers.tf has no bifrost provider requirement"
    assert 'version = "~>0.1.0"' in block.group(1)


def test_smoke_expects_the_renamed_refusal() -> None:
    smoke = (REPO_ROOT / "scripts" / "bifrost_smoke.py").read_text()
    assert '("access_not_found", {"x-bf-vk":' in smoke
    assert '("virtual_key_not_found",' not in smoke
