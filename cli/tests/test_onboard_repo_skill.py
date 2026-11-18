"""The onboard-repo skill stays tracked, cites real paths, and prints a safe caller workflow."""

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / ".claude" / "skills" / "onboard-repo" / "SKILL.md"
LAB_AUTH = REPO_ROOT / ".github" / "actions" / "lab-auth" / "action.yml"
OV_SYNC = REPO_ROOT / ".github" / "actions" / "openviking-sync" / "action.yml"


def _front_matter() -> dict[str, Any]:
    match = re.match(r"---\n(.*?)\n---\n", SKILL.read_text(), re.S)
    assert match, "SKILL.md has no front matter"
    loaded: dict[str, Any] = yaml.safe_load(match.group(1))
    return loaded


def _caller_workflow() -> dict[Any, Any]:
    blocks = re.findall(r"```yaml\n(.*?)```", SKILL.read_text(), re.S)
    workflows = [b for b in blocks if ".github/actions/lab-auth@" in b]
    assert len(workflows) == 1, "the skill needs exactly one caller workflow template"
    loaded: dict[Any, Any] = yaml.safe_load(workflows[0])
    return loaded


def test_skill_is_tracked_and_named() -> None:
    assert SKILL.is_file()
    ignored = subprocess.run(["git", "check-ignore", "-q", str(SKILL)], cwd=REPO_ROOT, check=False)
    assert ignored.returncode == 1, ".gitignore ignores the skill"
    front = _front_matter()
    assert front["name"] == "onboard-repo"
    assert front.get("description")


def test_cited_paths_exist() -> None:
    text = SKILL.read_text()
    cited = {
        p
        for p in re.findall(r"`([^`\s<>]+)`", text)
        if "/" in p and re.search(r"\.[a-z]+$|/$", p) and not p.startswith(("http", "JasperHG90"))
    }
    assert cited, "the skill cites no repository paths"
    missing = sorted(p for p in cited if not (REPO_ROOT / p.removeprefix("./")).exists())
    assert missing == []


def test_caller_workflow_template() -> None:
    workflow = _caller_workflow()
    # PyYAML reads the bare key `on` as the boolean True.
    on = workflow.get("on", workflow.get(True))
    assert not set(on or []) & {"pull_request", "pull_request_target"}
    assert workflow["permissions"]["id-token"] == "write"
    (job,) = workflow["jobs"].values()
    assert job["environment"] == "lab"
    declared = {
        "lab-auth": set(yaml.safe_load(LAB_AUTH.read_text())["inputs"]),
        "openviking-sync": set(yaml.safe_load(OV_SYNC.read_text())["inputs"]),
    }
    for step in job["steps"]:
        uses = step.get("uses", "")
        action = next((name for name in declared if f".github/actions/{name}@" in uses), None)
        if action is None:
            continue
        given = set(step.get("with") or {})
        assert given <= declared[action], f"{action} has no input {given - declared[action]}"
        assert not given & {"tailscale-client-id", "tailscale-audience"}
