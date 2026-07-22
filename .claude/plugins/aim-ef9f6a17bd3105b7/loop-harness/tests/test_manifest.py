"""Plugin manifest integrity: every declared skill and agent resolves.

The round-1 review caught an ``agents`` entry that pointed nowhere and an
invalid manifest shape. ``claude plugin validate`` catches the schema; these
tests catch drift the schema does not — a declared file that was deleted, or a
skill/agent added to the tree but never wired into the manifest.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def test_declared_agents_all_resolve_to_files() -> None:
    """Every plugin.json agents entry points at a real markdown file."""
    declared = MANIFEST.get("agents", [])
    assert isinstance(declared, list), "agents must be an array of file paths"
    for rel in declared:
        assert (PLUGIN_ROOT / rel).is_file(), f"declared agent missing: {rel}"


def test_every_agent_file_is_declared() -> None:
    """No agent file rides along undeclared (it would never register)."""
    on_disk = {f"./agents/{p.name}" for p in (PLUGIN_ROOT / "agents").glob("*.md")}
    declared = set(MANIFEST.get("agents", []))
    assert on_disk == declared, f"agents drift: on-disk={on_disk} declared={declared}"


def test_skills_dir_is_declared_and_each_has_a_skill_md() -> None:
    """The skills dir is wired, and every skill subdir carries a SKILL.md."""
    assert MANIFEST.get("skills") == "./skills/"
    skills_dir = PLUGIN_ROOT / "skills"
    subdirs = [p for p in skills_dir.iterdir() if p.is_dir()]
    assert subdirs, "no skills found"
    for sub in subdirs:
        assert (sub / "SKILL.md").is_file(), f"skill missing SKILL.md: {sub.name}"


def test_ticket_authoring_pair_is_present() -> None:
    """The create-ticket skill and its ticket-planner agent ship together:
    the skill is the contract, the agent authors against it."""
    assert (PLUGIN_ROOT / "skills" / "create-ticket" / "SKILL.md").is_file()
    assert (PLUGIN_ROOT / "agents" / "ticket-planner.md").is_file()
    assert "./agents/ticket-planner.md" in MANIFEST.get("agents", [])


def test_create_eval_skill_is_present() -> None:
    """The create-eval skill ships (auto-registered via the skills glob):
    it is the interactive producer of the eval marker the require_eval gate checks."""
    assert (PLUGIN_ROOT / "skills" / "create-eval" / "SKILL.md").is_file()


def test_init_loop_skill_is_present() -> None:
    """The init-loop skill ships (auto-registered via the skills glob):
    it is the guided path that bootstraps the harness into a consumer repo."""
    assert (PLUGIN_ROOT / "skills" / "init-loop" / "SKILL.md").is_file()


def test_review_pass_agents_are_present_and_declared() -> None:
    """The built-in review-pass agents ship and are wired into the manifest.

    A review pass names its agent in `.loop/config.json`; the harness
    dispatches that agent by name, so a missing or undeclared file means the
    pass cannot run.
    """
    for name in ("loop-reviewer", "loop-architect", "loop-doc-reviewer"):
        assert (PLUGIN_ROOT / "agents" / f"{name}.md").is_file()
        assert f"./agents/{name}.md" in MANIFEST.get("agents", [])


def test_doc_writer_action_agent_is_present_and_declared() -> None:
    """The built-in doc-writer action agent ships and is wired into the manifest.

    The `update-documentation` action stage dispatches this agent by name, so a
    missing or undeclared file means the stage cannot run.
    """
    assert (PLUGIN_ROOT / "agents" / "loop-doc-writer.md").is_file()
    assert "./agents/loop-doc-writer.md" in MANIFEST.get("agents", [])


def test_pyproject_version_derives_from_plugin_json() -> None:
    """The package version is single-sourced from the plugin manifest.

    The release-claude-code-plugin skill bumps only plugin.json; pyproject
    derives its version from it via hatchling's regex source. This reproduces
    that resolution so the wiring fails loudly if it drifts or the numbers
    diverge — no build required.
    """
    pyproject = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    # The version must be dynamic, not restated — a static value would drift.
    assert "version" in pyproject["project"].get("dynamic", []), "version must be dynamic"
    assert "version" not in pyproject["project"], "no static version alongside the dynamic one"

    hatch_version = pyproject["tool"]["hatch"]["version"]
    assert hatch_version["path"] == ".claude-plugin/plugin.json"

    source = (PLUGIN_ROOT / hatch_version["path"]).read_text(encoding="utf-8")
    match = re.search(hatch_version["pattern"], source)
    assert match is not None, "hatch version pattern does not match plugin.json"
    assert match.group("version") == MANIFEST["version"], (
        "derived version diverges from plugin.json"
    )
