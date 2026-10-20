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


def test_hermes_version_matches_the_base() -> None:
    pins = re.findall(r'hermes_version\s*=\s*"([^"]+)"', (APPS / "services.tf").read_text())
    assert pins == ["0.22.2-1"]


def test_config_keeps_openviking_and_sessions() -> None:
    hcl = (APPS / "services" / "hermes.hcl").read_text()
    memory = re.search(r"^memory:\n((?:  .*\n)+)", hcl, re.M)
    assert memory and 'provider: "openviking"' in memory.group(1)
    sessions = re.search(r"^sessions:\n((?:  .*\n)+)", hcl, re.M)
    assert sessions and "auto_prune: false" in sessions.group(1)


def test_recall_fits_inside_hermes_prefetch_limit() -> None:
    # Plugin 2.1.1 gives recall 3s per request and 4s in all; our memory
    # search takes 3.5-7s, so at the defaults recall always timed out. Hermes
    # drops a recall still running at 8s (_EXTERNAL_PREFETCH_TIMEOUT_S in
    # agent/memory_manager.py, not configurable), so a budget at or past 8s
    # waits for an answer it then throws away.
    hcl = (APPS / "services" / "hermes.hcl").read_text()
    block = re.search(r"^  openviking:\n((?:    .*\n)+)", hcl, re.M)
    assert block, "memory.openviking is missing from the Hermes config"
    settings = dict(re.findall(r"^    (\w+): (\S+)$", block.group(1), re.M))
    total = float(settings["recall_timeout_seconds"])
    request = float(settings["recall_request_timeout_seconds"])
    assert 7 <= total < 8
    assert request <= total
    # Full-content reads after the search would push the total past 8s.
    assert settings["recall_prefer_abstract"] == "true"
