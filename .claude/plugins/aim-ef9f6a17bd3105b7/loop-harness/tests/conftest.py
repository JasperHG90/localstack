"""Shared fixture: a real throwaway git repo (never mock the git layer)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real, seeded throwaway git repo."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "loop@test.local")
    git(tmp_path, "config", "user.name", "loop-test")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "seed commit")
    return tmp_path
