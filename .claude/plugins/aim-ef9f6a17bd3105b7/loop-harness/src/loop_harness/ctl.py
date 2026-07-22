"""Blessed ledger transitions: the only supported way to move a ticket.

Every transition passes through ``validate_transition`` with LIVE
evidence (stamp verdict, tree fingerprint, tree-bound PASSING reviewer
verdict), so a protocol slip fails loudly instead of relying on agent
discipline. Direct Edit/Write calls on ``.loop/ledger.json`` are blocked
by the state-guard hook; the ``loopctl`` CLI is the supported write path.

Known residual (accepted): an agent shelling out to ad-hoc Python can
still write the ledger directly — the guard raises the activation
energy, and the commit gate re-derives everything from evidence anyway,
so a hand-edited stage cannot smuggle an unreviewed commit through.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from loop_harness import halt as halt_mod
from loop_harness.config import load_config
from loop_harness.evals import eval_marker_present
from loop_harness.hooks import VERDICTS_DIR, pass_verdict_tree
from loop_harness.ledger import (
    Blocker,
    BlockerCode,
    Stage,
    TicketEntry,
    load_ledger,
    save_ledger,
)
from loop_harness.lifecycle import validate_transition
from loop_harness.reconcile import commit_for_slug
from loop_harness.reflection import verify_reflection
from loop_harness.stamp import tree_fingerprint, verify_stamp


def register(repo: Path, slug: str) -> str:
    """Register a ticket as ready; a no-op message when already present.

    Re-registering a ``dropped`` slug clears the dropped flag (the un-drop /
    restore path), preserving its stage. A present, non-dropped slug keeps the
    exact no-op so reconcile's idempotent auto-registration never disturbs it.
    """
    ledger = load_ledger(repo)
    existing = ledger.entries.get(slug)
    if existing is not None:
        if existing.dropped:
            existing.dropped = False
            save_ledger(repo, ledger)
            return f"{slug}: re-registered (un-dropped, {existing.stage.value})"
        return f"{slug}: already registered ({existing.stage.value})"
    ledger.entries[slug] = TicketEntry(slug=slug)
    save_ledger(repo, ledger)
    return f"{slug}: registered (ready)"


def drop(repo: Path, slug: str) -> str:
    """Retire a registered ticket: mark it dropped without deleting the entry.

    Drop is a reversible retirement, orthogonal to the lifecycle stage. The
    entry stays in the ledger (with its stage preserved), which is exactly what
    stops reconcile from resurrecting a dropped ticket off its surviving plan
    file. ``loopctl register <slug>`` restores it.

    Raises
    ------
    SystemExit
        If the slug is not registered (nothing to drop).
    """
    ledger = load_ledger(repo)
    if slug not in ledger.entries:
        raise SystemExit(f"{slug}: not registered - nothing to drop")
    ledger.entries[slug].dropped = True
    save_ledger(repo, ledger)
    return f"{slug}: dropped (reversible; `loopctl register {slug}` to restore)"


def advance(repo: Path, slug: str, target: Stage) -> str:
    """Validate a transition against live evidence, then apply it.

    Side effects follow the lifecycle: entering ``implementing`` bumps
    ``attempts``; the findings loop (adversarial-review back to gates)
    bumps ``review_cycles``; entering ``adversarial-review`` records the
    expected verdict path; returning to ``ready`` clears the blocker.

    Raises
    ------
    KeyError
        If the slug is not registered.
    LifecycleError
        If the transition's entry criteria are not met.
    """
    ledger = load_ledger(repo)
    entry = ledger.entries[slug]
    config = load_config(repo)
    passes = config.enabled_review_passes()
    validate_transition(
        entry.stage,
        target,
        stamp=verify_stamp(repo, config.fingerprint_ignore),
        pass_verdict_trees=[(p.id, pass_verdict_tree(repo, slug, p)) for p in passes],
        current_tree=tree_fingerprint(repo, config.fingerprint_ignore),
        review_cycles=entry.review_cycles,
        max_review_cycles=config.max_review_cycles,
        require_eval=config.require_eval,
        eval_marker_present=(
            eval_marker_present(repo, slug) if target is Stage.IMPLEMENTING else False
        ),
    )
    before = entry.stage
    if target is Stage.IMPLEMENTING:
        entry.attempts += 1
    if before is Stage.ADVERSARIAL_REVIEW and target is Stage.GATES:
        entry.review_cycles += 1
    if target is Stage.ADVERSARIAL_REVIEW:
        entry.review_verdict = (
            ", ".join(str(VERDICTS_DIR / p.verdict_filename(slug)) for p in passes) or None
        )
    if target is Stage.READY:
        entry.blocker = None
    entry.stage = target
    save_ledger(repo, ledger)
    return f"{slug}: {before.value} -> {target.value}"


def block(repo: Path, slug: str, code: BlockerCode, reason: str) -> str:
    """Move a ticket to blocked with a coded reason; notify the operator."""
    ledger = load_ledger(repo)
    entry = ledger.entries[slug]
    validate_transition(entry.stage, Stage.BLOCKED)
    entry.stage = Stage.BLOCKED
    entry.blocker = Blocker(code=code, reason=reason)
    save_ledger(repo, ledger)
    halt_mod.handoff(repo, f"{slug}: blocked ({code.value}) - {reason}")
    halt_mod.notify(f"loop: {slug} blocked ({code.value})", title=load_config(repo).notify_title)
    return f"{slug}: blocked ({code.value})"


def done(repo: Path, slug: str) -> str:
    """Close a ticket: requires the slug-anchored commit and a valid reflection.

    ``commit_sha`` is deliberately left to the reconciler (git is ground
    truth), so folding the ledger update into the ticket commit via
    ``--amend`` cannot store a stale hash. The reflection artifact must exist
    and satisfy the schema (DECISIONS.md R1); its prose is never graded.
    """
    ledger = load_ledger(repo)
    entry = ledger.entries[slug]
    sha = commit_for_slug(repo, slug)
    if sha is None:
        raise SystemExit(f"{slug}: no commit with subject '{slug}: ...' found - commit first")
    reflection = verify_reflection(repo, slug)
    if not reflection.ok:
        raise SystemExit(
            f"{slug}: reflection {reflection.status.value} - {reflection.detail}; "
            f"run `loopctl reflect {slug}`"
        )
    validate_transition(entry.stage, Stage.DONE)
    entry.stage = Stage.DONE
    save_ledger(repo, ledger)
    halt_mod.handoff(repo, f"{slug}: done (commit {sha[:10]})")
    halt_mod.notify(f"loop: {slug} done ({sha[:10]})", title=load_config(repo).notify_title)
    return f"{slug}: done (commit {sha[:10]})"


def main(argv: list[str] | None = None) -> int:
    """CLI dispatch for the blessed ledger transitions."""
    parser = argparse.ArgumentParser(description="loop ledger control")
    sub = parser.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("slug")
    adv = sub.add_parser("advance")
    adv.add_argument("slug")
    # BLOCKED goes through `block` (needs a coded reason); DONE goes through
    # `done` (needs the slug-anchored commit to exist)
    adv.add_argument(
        "stage",
        choices=[s.value for s in Stage if s not in (Stage.BLOCKED, Stage.DONE)],
    )
    blk = sub.add_parser("block")
    blk.add_argument("slug")
    blk.add_argument("code", choices=[c.value for c in BlockerCode])
    blk.add_argument("reason")
    dn = sub.add_parser("done")
    dn.add_argument("slug")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    if args.cmd == "register":
        print(register(repo, args.slug))
    elif args.cmd == "advance":
        print(advance(repo, args.slug, Stage(args.stage)))
    elif args.cmd == "block":
        print(block(repo, args.slug, BlockerCode(args.code), args.reason))
    else:
        print(done(repo, args.slug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
