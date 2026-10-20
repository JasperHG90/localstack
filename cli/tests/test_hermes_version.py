"""Drift tests: Hermes's base, its OpenViking plugin and its config move together.

v0.22 moved the OpenViking memory provider out of the base image, and turned
on pruning of ended sessions; either change slips by silently if the image or
config falls behind (spike:hermes-update/2, /3).
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"
DOCKERFILE = APPS / "services" / "hermes" / "Dockerfile"
PLUGIN_SHA = "9f150ece247ad683494ab172d738023bd6dc6170"


def test_base_is_v0_22_2() -> None:
    assert re.findall(r"^FROM (\S+)", DOCKERFILE.read_text(), re.M) == [
        "nousresearch/hermes-agent:v0.22.2"
    ]


def test_openviking_plugin_is_copied_in_pinned() -> None:
    text = DOCKERFILE.read_text()
    assert f"ARG OPENVIKING_PLUGIN_SHA={PLUGIN_SHA}" in text
    # The download must use that pin, not a branch.
    assert "codeload.github.com/volcengine/OpenViking/tar.gz/${OPENVIKING_PLUGIN_SHA}" in text
    assert '"OpenViking-${OPENVIKING_PLUGIN_SHA}/examples/hermes-plugin"' in text
    assert "/opt/hermes/plugins/memory/openviking" in text
    assert "examples/hermes-plugin" in text
    assert "version: 2.1.1" in text


def test_openviking_tools_wrapper_is_copied_beside_the_plugin() -> None:
    assert (DOCKERFILE.parent / "openviking_tools" / "__init__.py").is_file()
    assert re.findall(r"^COPY (.+)$", DOCKERFILE.read_text(), re.M) == [
        "openviking_tools /opt/hermes/plugins/memory/openviking_tools"
    ]


def test_hermes_version_matches_the_base() -> None:
    pins = re.findall(r'hermes_version\s*=\s*"([^"]+)"', (APPS / "services.tf").read_text())
    assert pins == ["0.22.2-2"]


def test_config_selects_openviking_tools_and_keeps_sessions() -> None:
    hcl = (APPS / "services" / "hermes.hcl").read_text()
    memory = re.search(r"^memory:\n((?:  .*\n)+)", hcl, re.M)
    assert memory
    assert re.findall(r"^  provider: (.+)$", memory.group(1), re.M) == ['"openviking_tools"']
    # Recall settings would only mislead: the wrapper never recalls.
    assert not re.search(r"^  openviking:|recall_", memory.group(1), re.M)
    sessions = re.search(r"^sessions:\n((?:  .*\n)+)", hcl, re.M)
    assert sessions and "auto_prune: false" in sessions.group(1)
