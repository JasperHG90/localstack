"""Blessed ledger transitions: evidence-checked at every step."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from loop_harness.config import CONFIG_FILE
from loop_harness.ctl import advance, block, done, register
from loop_harness.hooks import VERDICTS_DIR
from loop_harness.ledger import BlockerCode, Stage, load_ledger
from loop_harness.lifecycle import LifecycleError
from loop_harness.reflection import REFLECTIONS_DIR
from loop_harness.stamp import (
    GateResult,
    StampStatus,
    tree_fingerprint,
    verify_stamp,
    write_stamp,
)

SLUG = "some-ticket"


def _write_verdict(repo: Path, verdict: str = "pass") -> None:
    """Write a tree-bound reviewer verdict for the current tree."""
    path = repo / VERDICTS_DIR / f"{SLUG}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"verdict: {verdict}\ntree: {tree_fingerprint(repo)}\n", encoding="utf-8")


def _write_reflection(repo: Path) -> None:
    """Write a schema-valid reflection so `done` can close the ticket."""
    path = repo / REFLECTIONS_DIR / f"{SLUG}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nslug: {SLUG}\ncycles: 0\ngates_red: 0\n"
        "blockers: []\nfriction: []\nworked: [tests-first]\nharness_change:\n---\n",
        encoding="utf-8",
    )


def _commit_slug(repo: Path) -> None:
    """Create the slug-anchored commit the reconciler and `done` expect."""
    (repo / "work.txt").write_text("done\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"{SLUG}: land the work"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_register_is_idempotent(repo: Path) -> None:
    """Register is idempotent."""
    assert "registered" in register(repo, SLUG)
    assert "already registered" in register(repo, SLUG)
    assert load_ledger(repo).entries[SLUG].stage is Stage.READY


def test_advance_to_implementing_bumps_attempts(repo: Path) -> None:
    """Advance to implementing bumps attempts."""
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    assert load_ledger(repo).entries[SLUG].attempts == 1


def test_advance_to_gates_refused_without_stamp(repo: Path) -> None:
    """Advance to gates refused without stamp."""
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    with pytest.raises(LifecycleError, match="fresh stamp"):
        advance(repo, SLUG, Stage.GATES)


def test_advance_refuses_stage_jumps(repo: Path) -> None:
    """Advance refuses stage jumps."""
    register(repo, SLUG)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    with pytest.raises(LifecycleError, match="jump"):
        advance(repo, SLUG, Stage.GATES)


def test_full_lifecycle_with_evidence(repo: Path) -> None:
    """Full lifecycle with evidence: register through done."""
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    advance(repo, SLUG, Stage.GATES)
    advance(repo, SLUG, Stage.SELF_REVIEW)
    advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
    entry = load_ledger(repo).entries[SLUG]
    # the recorded (informational) path is the enabled pass's namespaced verdict file
    assert entry.review_verdict == str(VERDICTS_DIR / f"{SLUG}.adversarial.md")
    with pytest.raises(LifecycleError, match="verdict"):
        advance(repo, SLUG, Stage.COMMIT)  # no verdict file yet
    _write_verdict(repo)  # writes the legacy <slug>.md; adversarial pass falls back to it
    advance(repo, SLUG, Stage.COMMIT)
    with pytest.raises(SystemExit, match="commit first"):
        done(repo, SLUG)
    _commit_slug(repo)
    with pytest.raises(SystemExit, match="reflection absent"):
        done(repo, SLUG)  # no reflection yet
    _write_reflection(repo)
    assert "done" in done(repo, SLUG)
    assert load_ledger(repo).entries[SLUG].stage is Stage.DONE


def test_findings_loop_counts_cycles_and_caps(repo: Path) -> None:
    """Three findings loops are allowed; the fourth is refused (cap)."""
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    advance(repo, SLUG, Stage.GATES)
    for expected_cycle in (1, 2, 3):
        advance(repo, SLUG, Stage.SELF_REVIEW)
        advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
        advance(repo, SLUG, Stage.GATES)
        assert load_ledger(repo).entries[SLUG].review_cycles == expected_cycle
    advance(repo, SLUG, Stage.SELF_REVIEW)
    advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
    with pytest.raises(LifecycleError, match="cap"):
        advance(repo, SLUG, Stage.GATES)


def test_advance_to_commit_needs_every_enabled_pass_verdict(repo: Path) -> None:
    """With two enabled passes, commit is refused until BOTH verdicts are tree-bound."""
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(
            {
                "gates": ["true"],
                "review_passes": [
                    {"id": "adversarial", "agent": "loop-reviewer"},
                    {"id": "architectural", "agent": "loop-architect", "baseline": "M.md"},
                ],
            }
        ),
        encoding="utf-8",
    )
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    advance(repo, SLUG, Stage.GATES)
    advance(repo, SLUG, Stage.SELF_REVIEW)
    advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
    _write_verdict(repo)  # adversarial, via the legacy <slug>.md fallback
    with pytest.raises(LifecycleError, match="architectural"):
        advance(repo, SLUG, Stage.COMMIT)  # architectural verdict still missing
    (repo / VERDICTS_DIR / f"{SLUG}.architectural.md").write_text(
        f"verdict: pass\ntree: {tree_fingerprint(repo)}\n", encoding="utf-8"
    )
    advance(repo, SLUG, Stage.COMMIT)
    assert load_ledger(repo).entries[SLUG].stage is Stage.COMMIT


def test_commit_requires_all_three_built_in_pass_verdicts(repo: Path) -> None:
    """The shipped pass ids (adversarial, architectural, documentation) each gate commit.

    Exercises the review-pass machinery end to end with namespaced verdict
    files (not the legacy fallback): commit is refused until every enabled
    pass has its own tree-bound verdict.
    """
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(
            {
                "gates": ["true"],
                "review_passes": [
                    {"id": "adversarial", "agent": "loop-reviewer"},
                    {"id": "architectural", "agent": "loop-architect", "baseline": "M.md"},
                    {"id": "documentation", "agent": "loop-doc-reviewer"},
                ],
            }
        ),
        encoding="utf-8",
    )
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    advance(repo, SLUG, Stage.GATES)
    advance(repo, SLUG, Stage.SELF_REVIEW)
    advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
    tree = tree_fingerprint(repo)
    vdir = repo / VERDICTS_DIR
    vdir.mkdir(parents=True, exist_ok=True)
    for pass_id in ("adversarial", "architectural"):  # two of three: still refused
        (vdir / f"{SLUG}.{pass_id}.md").write_text(
            f"verdict: pass\ntree: {tree}\n", encoding="utf-8"
        )
    with pytest.raises(LifecycleError, match="documentation"):
        advance(repo, SLUG, Stage.COMMIT)
    (vdir / f"{SLUG}.documentation.md").write_text(
        f"verdict: pass\ntree: {tree}\n", encoding="utf-8"
    )
    advance(repo, SLUG, Stage.COMMIT)
    assert load_ledger(repo).entries[SLUG].stage is Stage.COMMIT


def test_action_stage_doc_edits_ride_the_stamped_tree(repo: Path) -> None:
    """A tree-mutating action stage run BEFORE the stamp lands in the committed tree.

    The `update-documentation` action edits docs during implementation; because
    those edits precede the stamp, they are in the stamped and verdict-bound
    tree and the commit is authorized. The same edit AFTER the stamp would
    stale it (the property the SKILL's before-stamp rule protects).
    """
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(
            {
                "gates": ["true"],
                "review_passes": [{"id": "adversarial", "agent": "loop-reviewer"}],
                "action_stages": [
                    {
                        "id": "update-documentation",
                        "type": "agent",
                        "ref": "loop-doc-writer",
                        "after": "implementing",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    (repo / "DOCS.md").write_text(
        "documented behavior\n", encoding="utf-8"
    )  # doc-writer, pre-stamp
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    advance(repo, SLUG, Stage.GATES)
    advance(repo, SLUG, Stage.SELF_REVIEW)
    advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
    _write_verdict(repo)  # bound to the tree that INCLUDES DOCS.md
    advance(repo, SLUG, Stage.COMMIT)  # allowed: docs are in the stamped/verdict tree
    assert load_ledger(repo).entries[SLUG].stage is Stage.COMMIT
    (repo / "DOCS.md").write_text("a late edit\n", encoding="utf-8")  # same edit, post-stamp
    assert verify_stamp(repo).status is StampStatus.STALE


def test_block_records_code_and_unblock_clears_it(repo: Path) -> None:
    """Block records code and unblock clears it."""
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    block(repo, SLUG, BlockerCode.UNRESOLVED_DESIGN_FORK, "Q1 unanswered")
    entry = load_ledger(repo).entries[SLUG]
    assert entry.stage is Stage.BLOCKED
    assert entry.blocker is not None
    assert entry.blocker.code is BlockerCode.UNRESOLVED_DESIGN_FORK
    advance(repo, SLUG, Stage.READY)
    entry = load_ledger(repo).entries[SLUG]
    assert entry.stage is Stage.READY
    assert entry.blocker is None


def test_commit_refused_when_verdict_tree_is_stale(repo: Path) -> None:
    """Commit refused when verdict tree is stale."""
    register(repo, SLUG)
    advance(repo, SLUG, Stage.IMPLEMENTING)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    advance(repo, SLUG, Stage.GATES)
    advance(repo, SLUG, Stage.SELF_REVIEW)
    advance(repo, SLUG, Stage.ADVERSARIAL_REVIEW)
    _write_verdict(repo)
    (repo / "README.md").write_text("tree moved\n", encoding="utf-8")
    write_stamp(
        repo, [GateResult("pytest", 0), GateResult("prek", 0)]
    )  # re-stamped, but verdict is stale
    with pytest.raises(LifecycleError, match="verdict"):
        advance(repo, SLUG, Stage.COMMIT)
