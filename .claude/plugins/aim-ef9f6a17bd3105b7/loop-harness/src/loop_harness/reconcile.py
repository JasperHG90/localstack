"""Git-is-ground-truth reconciliation for the ticket ledger.

Convention (consumed here, produced by the implement-ticket skill): a
ticket's commit subject contains its slug, canonically ``<slug>: summary``.
On every wake the loop reconciles: if the ledger claims done but no commit
carries the slug, the ledger is wrong; if a commit exists but the ledger
lags (crash between commit and ledger save), the ledger advances.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from loop_harness.ledger import Ledger, Stage, load_ledger, save_ledger

_DONE_STAGES = frozenset({Stage.COMMIT, Stage.DONE})


@dataclass(frozen=True)
class Correction:
    """One ledger correction made because git disagreed."""

    slug: str
    before: Stage
    after: Stage
    reason: str


def commit_for_slug(repo: Path, slug: str) -> str | None:
    """First commit whose subject matches ``<slug>: summary``, or ``None``.

    Anchored at the subject start with the colon delimiter: a bare
    substring match mis-attributes commits when one slug is a prefix of
    another (e.g. ``some-ticket`` vs ``some-ticket-2``).
    """
    result = subprocess.run(
        ["git", "log", "--format=%H%x09%s"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition("\t")
        if subject.startswith(f"{slug}:"):
            return sha
    return None


def reconcile(repo: Path, ledger: Ledger) -> list[Correction]:
    """Correct the ledger from git. Mutates ``ledger``; returns corrections."""
    corrections: list[Correction] = []
    for entry in ledger.entries.values():
        sha = commit_for_slug(repo, entry.slug)
        if entry.stage in _DONE_STAGES and sha is None:
            corrections.append(
                Correction(
                    slug=entry.slug,
                    before=entry.stage,
                    after=Stage.IMPLEMENTING,
                    reason="ledger claims done but no commit carries the slug; git wins",
                )
            )
            entry.stage = Stage.IMPLEMENTING
            entry.commit_sha = None
        elif entry.stage not in _DONE_STAGES and entry.stage is not Stage.BLOCKED and sha:
            corrections.append(
                Correction(
                    slug=entry.slug,
                    before=entry.stage,
                    after=Stage.DONE,
                    reason=f"commit {sha[:10]} carries the slug; git wins",
                )
            )
            entry.stage = Stage.DONE
            entry.commit_sha = sha
    return corrections


def main() -> int:
    """CLI: reconcile the ledger against git and report corrections."""
    repo = Path.cwd()
    ledger = load_ledger(repo)
    corrections = reconcile(repo, ledger)
    if corrections:
        save_ledger(repo, ledger)
        for c in corrections:
            print(f"{c.slug}: {c.before.value} -> {c.after.value} ({c.reason})")
    else:
        print("ledger consistent with git")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
