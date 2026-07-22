"""Reconcile: git is ground truth, in both directions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from loop_harness.config import CONFIG_FILE, load_config
from loop_harness.ledger import Blocker, BlockerCode, Ledger, Stage, TicketEntry
from loop_harness.reconcile import (
    commit_for_slug,
    reconcile,
    reconcile_plans,
    resolve_plans_dir,
)

SLUG = "broker-adapter-correctness-fixes"


def _setup_plans(repo: Path, plans_dir: str = ".loop/plans", slugs: tuple[str, ...] = ()) -> Path:
    """Write a config with ``plans_dir`` and create the given plan files."""
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"gates": ["true"], "plans_dir": plans_dir}), encoding="utf-8")
    pdir = repo / plans_dir
    pdir.mkdir(parents=True, exist_ok=True)
    for s in slugs:
        (pdir / f"{s}.md").write_text(f"# {s}\n", encoding="utf-8")
    return pdir


def test_reconcile_plans_auto_registers_orphan(repo: Path) -> None:
    """A plan file with no ledger entry is auto-registered at `ready`."""
    _setup_plans(repo, slugs=("orphan-a",))
    ledger = Ledger()
    registered, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert registered == ["orphan-a"]
    assert ledger.entries["orphan-a"].stage is Stage.READY
    assert warnings == []


def test_reconcile_plans_leaves_existing_entry_untouched(repo: Path) -> None:
    """An entry already present is never resurrected or duplicated."""
    _setup_plans(repo, slugs=("t1",))
    ledger = Ledger(entries={"t1": TicketEntry(slug="t1", stage=Stage.IMPLEMENTING)})
    registered, _ = reconcile_plans(repo, ledger, load_config(repo))
    assert registered == []
    assert ledger.entries["t1"].stage is Stage.IMPLEMENTING
    assert len(ledger.entries) == 1


def test_reconcile_plans_warns_on_non_terminal_missing_plan(repo: Path) -> None:
    """A non-terminal entry whose plan vanished warns and is NOT deleted."""
    _setup_plans(repo, slugs=())
    ledger = Ledger(entries={"t1": TicketEntry(slug="t1", stage=Stage.IMPLEMENTING)})
    registered, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert registered == []
    assert "t1" in ledger.entries
    assert any("t1" in w for w in warnings)


def test_reconcile_plans_silent_on_done_missing_plan(repo: Path) -> None:
    """A `done` entry with no plan file is silent (the archived-plan case)."""
    _setup_plans(repo, slugs=())
    ledger = Ledger(entries={"t1": TicketEntry(slug="t1", stage=Stage.DONE)})
    _, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert warnings == []


def test_reconcile_plans_is_idempotent(repo: Path) -> None:
    """A second reconcile registers nothing new and duplicates nothing."""
    _setup_plans(repo, slugs=("t1",))
    ledger = Ledger()
    reconcile_plans(repo, ledger, load_config(repo))
    registered2, _ = reconcile_plans(repo, ledger, load_config(repo))
    assert registered2 == []
    assert len(ledger.entries) == 1


def test_reconcile_plans_ignores_shared_home_plans_dir(repo: Path) -> None:
    """A `plans_dir` resolving OUTSIDE the repo (the shared-home default) pulls
    no plans into this ledger."""
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps({"gates": ["true"], "plans_dir": "~/.claude/plans"}), encoding="utf-8"
    )
    config = load_config(repo)
    assert resolve_plans_dir(repo, config) is None
    ledger = Ledger()
    registered, _ = reconcile_plans(repo, ledger, config)
    assert registered == []


def test_reconcile_plans_never_resurrects_dropped(repo: Path) -> None:
    """A dropped entry with a surviving plan file is NOT re-registered."""
    _setup_plans(repo, slugs=("t1",))
    ledger = Ledger(entries={"t1": TicketEntry(slug="t1", stage=Stage.READY, dropped=True)})
    registered, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert registered == []
    assert ledger.entries["t1"].dropped is True
    assert warnings == []


def test_reconcile_plans_silent_on_dropped_missing_plan(repo: Path) -> None:
    """A dropped entry whose plan is also gone yields no reverse-orphan warning."""
    _setup_plans(repo, slugs=())
    ledger = Ledger(entries={"t1": TicketEntry(slug="t1", stage=Stage.IMPLEMENTING, dropped=True)})
    _, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert warnings == []


def test_reconcile_plans_silent_on_blocked_missing_plan(repo: Path) -> None:
    """A `blocked` entry with no plan is silent (its plan may be intentionally
    gone); it is part of the non-warning set alongside `done` and `dropped`."""
    _setup_plans(repo, slugs=())
    ledger = Ledger(entries={"t1": TicketEntry(slug="t1", stage=Stage.BLOCKED)})
    _, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert warnings == []


def test_reconcile_plans_absent_dir_is_noop(repo: Path) -> None:
    """A configured `plans_dir` that does not exist on disk is a clean no-op."""
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"gates": ["true"], "plans_dir": ".loop/plans"}), encoding="utf-8")
    # deliberately do NOT create .loop/plans
    ledger = Ledger()
    registered, warnings = reconcile_plans(repo, ledger, load_config(repo))
    assert registered == []
    assert warnings == []


def test_reconcile_plans_then_git_self_heals_committed_orphan(repo: Path) -> None:
    """R7 ordering: an orphan plan whose slug-anchored commit already exists is
    registered by the plans pass and then upgraded to `done` by the git pass in
    the one reconcile run."""
    _setup_plans(repo, slugs=("healed-x",))
    _commit(repo, "healed-x: already shipped")
    ledger = Ledger()
    registered, _ = reconcile_plans(repo, ledger, load_config(repo))  # plans pass registers
    assert registered == ["healed-x"]
    reconcile(repo, ledger)  # git pass upgrades a slug a commit carries
    assert ledger.entries["healed-x"].stage is Stage.DONE


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
