"""Drift tests: Hermes's base, its OpenViking plugin and its config move together.

v0.22 moved the OpenViking memory provider out of the base image, and turned
on pruning of ended sessions; either change slips by silently if the image or
config falls behind (spike:hermes-update/2, /3). Voice notes need a speech
engine the base image lacks, pinned to the base's own lock file
(spike:ov-save-skill/8, /10).
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"
DOCKERFILE = APPS / "services" / "hermes" / "Dockerfile"
PLUGIN_SHA = "9f150ece247ad683494ab172d738023bd6dc6170"
UV = "/opt/hermes/tools/uv-0.12.3-linux-arm64/uv"
WHISPER_RUN = (
    f"RUN cd /opt/hermes && {UV} export --frozen --no-hashes --extra stt-whisper"
    " --no-emit-project -q -o /tmp/stt.txt"
    f" && {UV} pip install --no-cache --python /opt/hermes/.venv/bin/python"
    " -c /tmp/stt.txt faster-whisper==1.2.1 && rm /tmp/stt.txt"
)


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
    assert pins == ["0.22.2-3"]


def test_config_selects_openviking_tools_and_keeps_sessions() -> None:
    hcl = (APPS / "services" / "hermes.hcl").read_text()
    memory = re.search(r"^memory:\n((?:  .*\n)+)", hcl, re.M)
    assert memory
    assert re.findall(r"^  provider: (.+)$", memory.group(1), re.M) == ['"openviking_tools"']
    # Recall settings would only mislead: the wrapper never recalls.
    assert not re.search(r"^  openviking:|recall_", memory.group(1), re.M)
    sessions = re.search(r"^sessions:\n((?:  .*\n)+)", hcl, re.M)
    assert sessions and "auto_prune: false" in sessions.group(1)


def test_faster_whisper_is_baked_in_pinned_to_the_base_lock() -> None:
    runs = re.findall(r"^RUN .+$", DOCKERFILE.read_text(), re.M)
    # An unpinned install pulls PyAV 19.0.1, which breaks every transcription.
    assert WHISPER_RUN in runs


def test_config_transcribes_locally_with_the_base_model() -> None:
    hcl = (APPS / "services" / "hermes.hcl").read_text()
    stt = re.search(r"^stt:\n((?:  .*\n)+)", hcl, re.M)
    assert stt
    assert re.findall(r"^  provider: (.+)$", stt.group(1), re.M) == ['"local"']
    local = re.search(r"^  local:\n((?:    .*\n)+)", stt.group(1), re.M)
    assert local
    assert re.findall(r"^    model: (.+)$", local.group(1), re.M) == ['"base"']


# Toolset names hermes-agent defines in toolsets.py at v0.22.2. Hermes skips an
# unknown name with only a log warning, so a typo here silently strips a
# platform of its tools.
KNOWN_TOOLSETS = frozenset(
    {
        "browser",
        "clarify",
        "code_execution",
        "cronjob",
        "delegation",
        "file",
        "image_gen",
        "memory",
        "search",
        "session_search",
        "skills",
        "terminal",
        "todo",
        "tts",
        "vision",
        "web",
    }
)


def test_platform_toolsets_name_only_known_toolsets() -> None:
    hcl = (APPS / "services" / "hermes.hcl").read_text()
    block = re.search(r"^platform_toolsets:\n((?:  .*\n)+)", hcl, re.M)
    assert block
    platforms = re.findall(r"^  (\w+):\n((?:    - .*\n)+)", block.group(1), re.M)
    assert {name for name, _ in platforms} == {"email", "telegram"}
    for name, entries in platforms:
        toolsets = re.findall(r"^    - (\S+)$", entries, re.M)
        assert set(toolsets) <= KNOWN_TOOLSETS, (name, set(toolsets) - KNOWN_TOOLSETS)
        assert "file" in toolsets, name


def test_skills_name_the_file_toolset_correctly() -> None:
    skills = APPS / "services" / "hermes" / "skills"
    wrong = [str(p) for p in skills.rglob("SKILL.md") if "`files` toolset" in p.read_text()]
    assert wrong == []
