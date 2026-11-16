"""scripts/tf_validate.sh inits a root only when it has no .terraform/.

A failed init must not leave a .terraform/ behind: the next run would skip
init and fail on missing providers until someone deleted it by hand.
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tf_validate.sh"
ROOTS = ["deployments/infrastructure", "deployments/applications"]

# Records each call as "<root> <subcommand> <args...>". With STUB_INIT_FAIL
# set, init creates .terraform/ and then fails, as a broken download does.
STUB = """#!/usr/bin/env bash
chdir=${1#-chdir=}
shift
echo "$chdir $*" >> "$STUB_LOG"
case "$1" in
  init)
    mkdir -p "$chdir/.terraform/providers"
    [ -z "${STUB_INIT_FAIL:-}" ]
    ;;
  validate)
    [ -z "${STUB_VALIDATE_FAIL:-}" ]
    ;;
esac
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for root in ROOTS:
        (repo / root).mkdir(parents=True)
    return repo


def run(repo: Path, **env: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir = repo.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "terraform"
    stub.write_text(STUB)
    stub.chmod(0o755)
    log = repo.parent / "calls.log"
    log.write_text("")
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=repo,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_LOG": str(log),
            **env,
        },
        capture_output=True,
        text=True,
    )
    return result, log.read_text().splitlines()


def test_failed_init_removes_the_terraform_dir_it_created(repo: Path) -> None:
    result, calls = run(repo, STUB_INIT_FAIL="1")

    assert result.returncode != 0
    assert calls[0].startswith(f"{ROOTS[0]} init")
    assert not (repo / ROOTS[0] / ".terraform").exists()


def test_existing_terraform_dir_is_never_initialized_or_removed(repo: Path) -> None:
    for root in ROOTS:
        (repo / root / ".terraform" / "terraform.tfstate").parent.mkdir()
        (repo / root / ".terraform" / "terraform.tfstate").write_text("backend\n")

    result, calls = run(repo, STUB_VALIDATE_FAIL="1")

    assert result.returncode != 0
    assert calls == [f"{ROOTS[0]} validate -no-color"]
    for root in ROOTS:
        assert (repo / root / ".terraform" / "terraform.tfstate").read_text() == "backend\n"


def test_fresh_root_is_initialized_without_backend_then_validated(repo: Path) -> None:
    result, calls = run(repo)

    assert result.returncode == 0, result.stderr
    assert calls == [
        line
        for root in ROOTS
        for line in (
            f"{root} init -backend=false -input=false -no-color",
            f"{root} validate -no-color",
        )
    ]
