"""Reconcile: git is ground truth, in both directions."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loop_harness.ledger import Blocker, BlockerCode, Ledger, Stage, TicketEntry
from loop_harness.reconcile import commit_for_slug, reconcile

SLUG = "broker-adapter-correctness-fixes"


def git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout


def _commit(repo: Path, subject: str) -> str:
    """Create a commit with the given subject; return its sha."""
    (repo / "work.txt").write_text(subject + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", subject)
    return git(repo, "rev-parse", "HEAD").strip()


def test_commit_for_slug_matches_anchored_subject(repo: Path) -> None:
    """The documented convention `<slug>: summary` resolves to its commit."""
    sha = _commit(repo, f"{SLUG}: fix TP restore on partial exit")
    assert commit_for_slug(repo, SLUG) == sha


def test_commit_for_slug_ignores_unrelated_subjects(repo: Path) -> None:
    """A subject without the slug never matches."""
    _commit(repo, "unrelated: housekeeping")
    assert commit_for_slug(repo, SLUG) is None


def test_commit_for_slug_rejects_prefix_collisions(repo: Path) -> None:
    """A commit for `<slug>-2` must never be attributed to `<slug>`."""
    _commit(repo, f"{SLUG}-2: land the sibling ticket")
    assert commit_for_slug(repo, SLUG) is None
    assert commit_for_slug(repo, f"{SLUG}-2") is not None


def test_commit_for_slug_requires_subject_anchor(repo: Path) -> None:
    """A slug mentioned mid-subject is not this ticket's commit."""
    _commit(repo, f"revert work on {SLUG}: cleanup")
    assert commit_for_slug(repo, SLUG) is None


def test_prefix_collision_does_not_corrupt_ledger(repo: Path) -> None:
    """Regression (adversarial review): the sibling ticket's commit must not
    flip an in-flight shorter-slug ticket to done."""
    _commit(repo, f"{SLUG}-2: land the sibling ticket")
    ledger = Ledger(entries={SLUG: TicketEntry(slug=SLUG, stage=Stage.IMPLEMENTING)})
    assert reconcile(repo, ledger) == []
    assert ledger.entries[SLUG].stage is Stage.IMPLEMENTING
    assert ledger.entries[SLUG].commit_sha is None


def test_ledger_claiming_done_without_commit_is_corrected(repo: Path) -> None:
    """Ledger claiming done without commit is corrected."""
    ledger = Ledger(entries={SLUG: TicketEntry(slug=SLUG, stage=Stage.DONE, commit_sha="deadbeef")})
    corrections = reconcile(repo, ledger)
    assert [c.slug for c in corrections] == [SLUG]
    entry = ledger.entries[SLUG]
    assert entry.stage is Stage.IMPLEMENTING
    assert entry.commit_sha is None


def test_ledger_lagging_behind_commit_is_advanced(repo: Path) -> None:
    """Ledger lagging behind commit is advanced."""
    sha = _commit(repo, f"{SLUG}: land the adapter fixes")
    ledger = Ledger(entries={SLUG: TicketEntry(slug=SLUG, stage=Stage.COMMIT)})
    # stage COMMIT counts as done-claimed; use a mid-flight stage instead
    ledger.entries[SLUG].stage = Stage.ADVERSARIAL_REVIEW
    corrections = reconcile(repo, ledger)
    assert [c.after for c in corrections] == [Stage.DONE]
    entry = ledger.entries[SLUG]
    assert entry.stage is Stage.DONE
    assert entry.commit_sha == sha


def test_blocked_entries_are_never_touched(repo: Path) -> None:
    """Blocked entries are never touched."""
    _commit(repo, f"{SLUG}: partial work landed before the block")
    ledger = Ledger(
        entries={
            SLUG: TicketEntry(
                slug=SLUG,
                stage=Stage.BLOCKED,
                blocker=Blocker(
                    code=BlockerCode.DISPUTED_REVIEWER_FINDING,
                    reason="escalated to operator",
                ),
            )
        }
    )
    assert reconcile(repo, ledger) == []
    assert ledger.entries[SLUG].stage is Stage.BLOCKED


def test_consistent_ledger_yields_no_corrections(repo: Path) -> None:
    """Consistent ledger yields no corrections."""
    sha = _commit(repo, f"{SLUG}: done and recorded")
    ledger = Ledger(entries={SLUG: TicketEntry(slug=SLUG, stage=Stage.DONE, commit_sha=sha)})
    assert reconcile(repo, ledger) == []
