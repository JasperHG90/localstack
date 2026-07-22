"""Git-level ``pre-commit`` backstop: install/uninstall lifecycle and real commits.

Every gate test drives a REAL ``git commit`` through the INSTALLED hook in a
real temp repo (never mocking git), because the backstop's whole value is
catching commit forms the PreToolUse string matcher cannot see.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from loop_harness import githook
from loop_harness.config import CONFIG_FILE
from loop_harness.githook import MARKER, install, uninstall
from loop_harness.ledger import LEDGER_FILE
from loop_harness.stamp import GateResult, write_stamp


def git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _make_consumer(repo: Path, *, green: bool) -> None:
    """Turn ``repo`` into a loop consumer, with a green stamp iff ``green``.

    Uses ``require_review: false`` so a green stamp alone authorizes a commit
    (no verdict files needed). Commit signing is disabled so headless commits
    work regardless of the operator's global git config.
    """
    git(repo, "config", "commit.gpgsign", "false")
    (repo / ".loop").mkdir(exist_ok=True)
    (repo / CONFIG_FILE).write_text(
        json.dumps({"gates": ["true"], "require_review": False, "review_passes": []}),
        encoding="utf-8",
    )
    if green:
        write_stamp(repo, [GateResult("true", 0)])


def _stage_change(repo: Path, name: str = "change.txt") -> None:
    """Create and stage a new file so a commit has real content to record."""
    (repo / name).write_text("content\n", encoding="utf-8")
    git(repo, "add", "-A")


def _commit_plain(repo: Path) -> subprocess.CompletedProcess[str]:
    """A bare ``git commit`` issued inside ``repo``."""
    return subprocess.run(["git", "commit", "-m", "x"], cwd=repo, capture_output=True, text=True)


def _commit_dash_c(repo: Path) -> subprocess.CompletedProcess[str]:
    """A ``git -C <repo> commit`` issued from OUTSIDE the repo."""
    return subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "x"],
        cwd=repo.parent,
        capture_output=True,
        text=True,
    )


def _commit_subprocess(repo: Path) -> subprocess.CompletedProcess[str]:
    """A commit shelled out from a python subprocess (no matchable Bash string)."""
    code = (
        "import subprocess, sys; "
        f"sys.exit(subprocess.run(['git', 'commit', '-m', 'x'], cwd={str(repo)!r}).returncode)"
    )
    return subprocess.run(
        [sys.executable, "-c", code], cwd=repo.parent, capture_output=True, text=True
    )


def _head_count(repo: Path) -> int:
    """Number of commits reachable from HEAD."""
    return int(git(repo, "rev-list", "--count", "HEAD").strip())


# --- 1. Backstop proves the gap: git itself blocks a stampless commit ---


@pytest.mark.parametrize(
    "commit",
    [_commit_plain, _commit_dash_c, _commit_subprocess],
    ids=["plain", "dash-C-from-elsewhere", "python-subprocess"],
)
def test_commit_without_stamp_is_blocked_by_git(
    repo: Path, commit: Callable[[Path], subprocess.CompletedProcess[str]]
) -> None:
    """With no green stamp, git rejects the commit for every §3 form."""
    _make_consumer(repo, green=False)
    assert install(repo).ok
    before = _head_count(repo)
    _stage_change(repo)
    result = commit(repo)
    assert result.returncode != 0
    assert "loop gate" in result.stderr
    assert _head_count(repo) == before  # nothing committed


# --- 2. Green evidence commits through the installed hook ---


def test_green_stamp_allows_commit(repo: Path) -> None:
    """A green stamp bound to the current tree lets the commit succeed."""
    _make_consumer(repo, green=False)
    assert install(repo).ok
    _stage_change(repo)
    write_stamp(repo, [GateResult("true", 0)])  # stamp AFTER staging: binds this tree
    before = _head_count(repo)
    result = _commit_plain(repo)
    assert result.returncode == 0, result.stderr
    assert _head_count(repo) == before + 1


# --- 3. HALT steps the git hook aside ---


def test_halt_lets_the_commit_through(repo: Path) -> None:
    """An engaged HALT bypasses the backstop even with no green evidence."""
    from loop_harness import halt as halt_mod

    _make_consumer(repo, green=False)
    assert install(repo).ok
    halt_mod.engage(repo, "operator in control")
    _stage_change(repo)
    before = _head_count(repo)
    result = _commit_plain(repo)
    assert result.returncode == 0, result.stderr
    assert _head_count(repo) == before + 1


# --- 4. A dormant repo (no .loop/) is unaffected ---


def test_dormant_repo_commit_unaffected(repo: Path) -> None:
    """With the hook installed but no .loop/, an ordinary commit succeeds."""
    git(repo, "config", "commit.gpgsign", "false")
    assert install(repo).ok  # no .loop/ present
    _stage_change(repo)
    before = _head_count(repo)
    result = _commit_plain(repo)
    assert result.returncode == 0, result.stderr
    assert _head_count(repo) == before + 1


# --- 5. An internal error in the entry fails OPEN ---


def test_internal_error_fails_open(repo: Path) -> None:
    """A corrupt ledger (would raise) allows the commit instead of wedging it."""
    _make_consumer(repo, green=False)  # no stamp: would fail SAFE (block) normally
    assert install(repo).ok
    (repo / LEDGER_FILE).write_text("{broken", encoding="utf-8")  # load_ledger raises
    _stage_change(repo)
    before = _head_count(repo)
    result = _commit_plain(repo)
    assert result.returncode == 0, result.stderr  # fail OPEN, not the fail-safe block
    assert "failing open" in result.stderr
    assert _head_count(repo) == before + 1


# --- 6. Non-destructive install + uninstall + idempotency ---


def test_install_refuses_existing_unmanaged_hook(repo: Path) -> None:
    """Install never clobbers a consumer's own pre-commit hook."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    result = install(repo)
    assert not result.ok
    assert "not" in result.message and "harness-managed" in result.message
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"  # untouched
    # uninstall must leave the unmanaged hook alone too
    assert uninstall(repo).ok
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"


def test_install_refuses_when_hookspath_is_set(repo: Path) -> None:
    """A set core.hooksPath makes install refuse rather than write an inert hook."""
    git(repo, "config", "core.hooksPath", ".githooks")
    result = install(repo)
    assert not result.ok
    assert "core.hooksPath" in result.message
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


def test_install_uninstall_roundtrip_and_idempotent(repo: Path) -> None:
    """Fresh install writes a managed hook; re-install is idempotent; uninstall restores."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    assert not hook.exists()  # git init writes only pre-commit.sample
    assert install(repo).ok
    assert hook.exists() and MARKER in hook.read_text(encoding="utf-8")
    first = hook.read_text(encoding="utf-8")
    # idempotent: re-running rewrites in place, never stacks a duplicate
    assert install(repo).ok
    assert hook.read_text(encoding="utf-8") == first
    # uninstall removes only the managed hook, restoring the prior (absent) state
    assert uninstall(repo).ok
    assert not hook.exists()
    # uninstall again is a no-op
    assert uninstall(repo).ok


def test_installed_hook_shim_points_at_the_plugin(repo: Path) -> None:
    """The generated hook bakes in the absolute path to the run_git_hook shim."""
    assert install(repo).ok
    body = (repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    shim = Path(githook.__file__).resolve().parents[2] / "scripts" / "run_git_hook.py"
    assert str(shim) in body
    assert shim.exists()
