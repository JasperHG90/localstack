"""The ci lint job puts every tool prek's system hooks call on the runner.

`nomad-fmt`, `terraform-fmt` and `terraform-validate` in .pre-commit-config.yaml
run binaries from PATH, and `terraform validate` reads the gitignored
`.ssh/id_rsa`. GitHub's runner has none of these, so each must come from a step
that runs before prek.
"""

from pathlib import Path
from typing import Any

import yaml

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
CI = REPO_ROOT / ".github" / "workflows" / "ci.yaml"

TERRAFORM_VERSION = "1.16.5"
NOMAD_VERSION = "2.0.4"


def _lint_steps() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = yaml.safe_load(CI.read_text())["jobs"]["lint"]["steps"]
    return steps


def _index(steps: list[dict[str, Any]], match: str) -> int:
    hits = [i for i, s in enumerate(steps) if match in s.get("uses", "") + s.get("run", "")]
    assert hits, f"no lint step mentions {match!r}"
    return hits[0]


def test_lint_job_installs_hook_tools_before_prek() -> None:
    steps = _lint_steps()
    prek = _index(steps, "prek")

    terraform = _index(steps, "hashicorp/setup-terraform")
    assert steps[terraform]["with"]["terraform_version"] == TERRAFORM_VERSION

    nomad = _index(steps, "releases.hashicorp.com/nomad")
    nomad_step = steps[nomad]
    script = nomad_step["run"].replace(
        "${NOMAD_VERSION}", nomad_step.get("env", {}).get("NOMAD_VERSION", "")
    )
    assert f"nomad_{NOMAD_VERSION}_linux_amd64.zip" in script
    assert f"nomad_{NOMAD_VERSION}_SHA256SUMS" in script
    assert "sha256sum -c" in script

    key = _index(steps, ".ssh/id_rsa")

    assert max(terraform, nomad, key) < prek


def test_prek_step_sets_nomad_addr() -> None:
    """Both roots' nomad providers take their address from NOMAD_ADDR, and
    terraform validate requires it even though it never connects."""
    steps = _lint_steps()
    prek = steps[_index(steps, "prek")]
    assert prek.get("env", {}).get("NOMAD_ADDR")
