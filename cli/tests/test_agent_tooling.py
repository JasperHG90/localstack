"""APM installs every rule, skill and subagent this repository uses; aim is gone.

The installed copies under .claude/ are gitignored, so these tests read what
is committed: apm.yml, the install recipes, the OpenCode copies and the docs.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from localstack_cli.versions import resolve_repo_root

SKILLS = [
    "manifesto",
    "deep-explain",
    "doc-write",
    "python-review",
    "readme-creator",
    "release",
    "generate-art",
    "remove-image-background",
    "agent-creator",
    "rule-creator",
    "adhd",
    "bencium-impact-designer",
]
APM_RULES = [
    "adversarial-reviews",
    "pre-existing-issues",
    "prek-code-quality",
    "python-testing",
    "uv-installer",
    "plain-language",
]
RULES = [*APM_RULES, "slop-scan-for-docs"]
SUBAGENTS = ["adversarial-reviewer", "feature-planner"]
# sha256 of the copy aim installed from athola/claude-night-market at b226e39.
SLOP_SCAN_SHA256 = "ccce6d06e1707ea75cc0c25a3a06f163b4faa778b4d9b6d9833681cabd74c486"
INSTALLER_PATHS = [
    ".agents/skills/audit/SKILL.md",
    ".opencode/rules/plain-language.md",
    "opencode.json",
    ".mcp.json",
    "apm.lock.yaml",
    ".claude/rules/okf-bundle.md",
    ".loop/plans/aim-to-apm.md",
]


def root() -> Path:
    return resolve_repo_root()


def apm_dependencies() -> list[str]:
    manifest = yaml.safe_load((root() / "apm.yml").read_text())
    deps = manifest["dependencies"]["apm"]
    return [
        d if isinstance(d, str) else f"{d['git']}/{d.get('path', '')}#{d.get('ref', '')}"
        for d in deps
    ]


def recipe(name: str) -> str:
    """The body of one justfile recipe: its header line up to the next blank line."""
    text = (root() / "justfile").read_text()
    match = re.search(rf"^{re.escape(name)}:.*?(?=^\S|\Z)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, f"justfile has no {name} recipe"
    return match.group(0)


def test_aim_is_gone() -> None:
    assert not (root() / "aim.toml").exists()
    assert not (root() / "aim.lock.toml").exists()
    agents_md = (root() / "AGENTS.md").read_text()
    assert "aim:" not in agents_md
    assert "agent-integrations-manager" not in agents_md
    claude_md = root() / "CLAUDE.md"
    assert claude_md.is_symlink()
    assert claude_md.resolve() == (root() / "AGENTS.md").resolve()


@pytest.mark.parametrize(
    "path",
    [f"/{s}#" for s in SKILLS]
    + [f"/rules/{r}.instructions.md#" for r in APM_RULES]
    + [f"/agents/{a}.agent.md#" for a in SUBAGENTS],
)
def test_apm_declares_the_tooling(path: str) -> None:
    assert any(path in dep for dep in apm_dependencies()), (
        f"apm.yml has no dependency ending {path}"
    )


def test_apm_declares_the_tooling_pinned() -> None:
    unpinned = [dep for dep in apm_dependencies() if not re.search(r"#[\w.-]+$", dep)]
    assert unpinned == []


@pytest.mark.parametrize("path", ["apm.yml", ".mcp.json"])
def test_mcp_servers_are_dropped(path: str) -> None:
    text = (root() / path).read_text().lower()
    assert "drawio" not in text
    assert "excalidraw" not in text


def test_slop_scan_is_vendored() -> None:
    rule = root() / ".claude" / "rules" / "slop-scan-for-docs.md"
    assert hashlib.sha256(rule.read_bytes()).hexdigest() == SLOP_SCAN_SHA256
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(rule.relative_to(root()))], cwd=root(), check=False
    )
    assert ignored.returncode == 1, "slop-scan-for-docs.md is gitignored"


@pytest.mark.parametrize("rule", RULES)
def test_opencode_rule_matches_the_claude_rule(rule: str) -> None:
    """Byte identity needs an installed .claude/rules, which is gitignored. On a
    checkout with no install, eval row r8's clean-checkout check-install proves it."""
    opencode = root() / ".opencode" / "rules" / f"{rule}.md"
    assert opencode.is_file(), f"{opencode} is missing"
    claude = root() / ".claude" / "rules" / f"{rule}.md"
    if claude.is_file():
        assert opencode.read_bytes() == claude.read_bytes()


@pytest.mark.parametrize("agent", SUBAGENTS)
def test_opencode_has_no_claude_only_subagent(agent: str) -> None:
    assert not (root() / ".opencode" / "agents" / f"{agent}.md").exists()


@pytest.mark.parametrize("name", ["kmctl-install", "kmctl-install-frozen"])
def test_opencode_rules_come_from_both_install_recipes(name: str) -> None:
    body = recipe(name)
    copied = re.findall(r"\.claude/rules/([^\s/]+?)\.md", body)
    assert sorted(set(copied)) == sorted(RULES), f"{name} copies {sorted(set(copied))}"
    assert ".claude/rules/*" not in body, f"{name} copies rules by glob"
    for agent in SUBAGENTS:
        assert f".opencode/agents/{agent}.md" in body, f"{name} does not remove {agent}"


@pytest.mark.parametrize("path", INSTALLER_PATHS)
def test_installer_owns_its_files(path: str) -> None:
    config = yaml.safe_load((root() / ".pre-commit-config.yaml").read_text())
    assert re.search(config["exclude"], path), f"pre-commit would rewrite {path}"


def kmctl_section() -> str:
    readme = (root() / "README.md").read_text()
    match = re.search(
        r"^## Knowledge management with kmctl\n(.*?)(?=^## )", readme, re.MULTILINE | re.DOTALL
    )
    assert match is not None
    return match.group(1)


def test_readme_documents_the_caveman_install() -> None:
    section = kmctl_section()
    assert "claude plugin marketplace add juliusbrussee/caveman" in section
    assert "claude plugin install caveman@caveman" in section


def test_readme_names_the_real_recipes() -> None:
    section = kmctl_section()
    assert re.findall(r"just (?:install|init|check)(?![\w-])", section) == []
    recipes = set(
        re.findall(r"^([\w-]+)(?: [^:=]*)?:(?!=)", (root() / "justfile").read_text(), re.MULTILINE)
    )
    for name in re.findall(r"`just ([\w-]+)`", section):
        assert name in recipes, f"README names just {name}, which the justfile does not define"


def test_opencode_json_still_loads_the_rules() -> None:
    assert (
        ".opencode/rules/*.md" in json.loads((root() / "opencode.json").read_text())["instructions"]
    )
