"""loopctl: the blessed CLI end to end in a real temp repo."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from loop_harness.cli import main
from loop_harness.config import CONFIG_FILE
from loop_harness.hooks import VERDICTS_DIR
from loop_harness.ledger import Stage, load_ledger
from loop_harness.reflection import REFLECTIONS_DIR
from loop_harness.stamp import tree_fingerprint


def _configure(repo: Path, gates: list[str]) -> None:
    """Author a loop config with the given gate commands."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gates": gates}), encoding="utf-8")


def _write_reflection(repo: Path, slug: str) -> None:
    """Write a schema-valid reflection so `finish` can close the ticket."""
    path = repo / REFLECTIONS_DIR / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nslug: {slug}\ncycles: 0\ngates_red: 0\n"
        "blockers: []\nfriction: []\nworked: [tests-first]\nharness_change:\n---\n",
        encoding="utf-8",
    )


def _run(repo: Path, *argv: str, monkeypatch: pytest.MonkeyPatch) -> int:
    """Invoke loopctl in ``repo`` (the CLI resolves the repo from cwd)."""
    monkeypatch.chdir(repo)
    return main(list(argv))


def test_init_scaffolds_config_once(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`loopctl init` writes the starter config and refuses a second run."""
    assert _run(repo, "init", monkeypatch=monkeypatch) == 0
    assert (repo / CONFIG_FILE).exists()
    assert _run(repo, "init", monkeypatch=monkeypatch) == 1


def test_stamp_runs_configured_gates(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`loopctl stamp` executes the configured commands and verifies green."""
    _configure(repo, ["true", "true"])
    assert _run(repo, "stamp", monkeypatch=monkeypatch) == 0
    assert _run(repo, "verify", monkeypatch=monkeypatch) == 0
    _configure(repo, ["true", "false"])
    assert _run(repo, "stamp", monkeypatch=monkeypatch) == 1
    assert _run(repo, "verify", monkeypatch=monkeypatch) == 1


def test_stamp_without_config_fails_loudly(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unconfigured consumer cannot certify a tree it never tested."""
    with pytest.raises(ValueError, match="no gates configured"):
        _run(repo, "stamp", monkeypatch=monkeypatch)


def test_finish_folds_ledger_into_the_slug_commit(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full close: done + amend + reconcile, guarded on HEAD and index."""
    slug = "some-ticket"
    _drive_to_slug_commit(repo, slug, monkeypatch)
    _write_reflection(repo, slug)
    assert _run(repo, "finish", slug, monkeypatch=monkeypatch) == 0
    assert load_ledger(repo).entries[slug].stage is Stage.DONE
    reflection_blob = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:.loop/reflections/{slug}.md"], cwd=repo, check=False
    )
    assert reflection_blob.returncode == 0  # the reflection rode the ticket commit
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert subject == f"{slug}: the work"  # the amend kept the reviewed commit
    count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert count == "2"  # initial + the (amended) ticket commit, no extra commit


def _drive_to_slug_commit(repo: Path, slug: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run a ticket through the lifecycle and land its slug-anchored commit."""
    _configure(repo, ["true"])
    assert _run(repo, "register", slug, monkeypatch=monkeypatch) == 0
    assert _run(repo, "advance", slug, "implementing", monkeypatch=monkeypatch) == 0
    assert _run(repo, "stamp", monkeypatch=monkeypatch) == 0
    assert _run(repo, "advance", slug, "gates", monkeypatch=monkeypatch) == 0
    assert _run(repo, "advance", slug, "self-review", monkeypatch=monkeypatch) == 0
    assert _run(repo, "advance", slug, "adversarial-review", monkeypatch=monkeypatch) == 0
    verdicts = repo / VERDICTS_DIR
    verdicts.mkdir(parents=True, exist_ok=True)
    (verdicts / f"{slug}.md").write_text(
        f"verdict: pass\ntree: {tree_fingerprint(repo)}\n", encoding="utf-8"
    )
    assert _run(repo, "stamp", monkeypatch=monkeypatch) == 0
    assert _run(repo, "advance", slug, "commit", monkeypatch=monkeypatch) == 0
    subprocess.run(["git", "add", "-A", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"{slug}: the work"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_finish_refuses_without_a_reflection(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`finish` refuses to close a ticket whose reflection is absent."""
    slug = "some-ticket"
    _drive_to_slug_commit(repo, slug, monkeypatch)
    with pytest.raises(SystemExit, match="reflection absent"):
        _run(repo, "finish", slug, monkeypatch=monkeypatch)
    assert load_ledger(repo).entries[slug].stage is Stage.COMMIT


def test_reflect_scaffolds_then_validates(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`loopctl reflect` scaffolds a valid template, then validates it green."""
    slug = "some-ticket"
    assert _run(repo, "register", slug, monkeypatch=monkeypatch) == 0
    assert _run(repo, "reflect", slug, monkeypatch=monkeypatch) == 0  # scaffolds
    assert (repo / REFLECTIONS_DIR / f"{slug}.md").exists()
    assert _run(repo, "reflect", slug, monkeypatch=monkeypatch) == 0  # validates the scaffold
    (repo / REFLECTIONS_DIR / f"{slug}.md").write_text(
        f"---\nslug: {slug}\ncycles: 0\n---\n", encoding="utf-8"
    )
    assert _run(repo, "reflect", slug, monkeypatch=monkeypatch) == 1  # now schema-invalid


def test_distill_runs_over_reflections(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`loopctl distill` aggregates reflections without error."""
    _write_reflection(repo, "some-ticket")
    assert _run(repo, "distill", monkeypatch=monkeypatch) == 0


def test_finish_refuses_wrong_head(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """finish is guarded: HEAD must be the slug-anchored commit."""
    _configure(repo, ["true"])
    assert _run(repo, "register", "some-ticket", monkeypatch=monkeypatch) == 0
    assert _run(repo, "finish", "some-ticket", monkeypatch=monkeypatch) == 1


def test_ledger_and_halt_round_trip(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """halt/resume/status and the ledger printout run end to end."""
    assert _run(repo, "halt", "drill", monkeypatch=monkeypatch) == 0
    assert _run(repo, "status", monkeypatch=monkeypatch) == 0
    assert _run(repo, "resume", monkeypatch=monkeypatch) == 0
    assert _run(repo, "ledger", monkeypatch=monkeypatch) == 0
    assert _run(repo, "reconcile", monkeypatch=monkeypatch) == 0
