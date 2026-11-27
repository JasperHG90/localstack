"""Drift tests: Bifrost's pin, its provider and the smoke script move together.

The 2.3.1 to 2.6.0 store migrations cannot be undone, and the smoke script
must keep expecting the unknown-key refusal 2.1.0 renamed, so a pin that moved
without its checks would fail them (spikes under .loop/spikes/bifrost-update-2-6/).
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"


def test_bifrost_is_pinned_to_2_7_0() -> None:
    pins = re.findall(r'bifrost_version\s*=\s*"([^"]+)"', (APPS / "services.tf").read_text())
    assert pins == ["2.7.0"]


def test_provider_stays_on_0_1() -> None:
    block = re.search(r"bifrost = \{(.*?)\}", (APPS / "providers.tf").read_text(), re.S)
    assert block, "providers.tf has no bifrost provider requirement"
    assert 'version = "~>0.1.0"' in block.group(1)


def test_smoke_expects_the_renamed_refusal() -> None:
    smoke = (REPO_ROOT / "scripts" / "bifrost_smoke.py").read_text()
    assert '("access_not_found", {"x-bf-vk":' in smoke
    assert '("virtual_key_not_found",' not in smoke
