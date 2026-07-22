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

from loop_harness.config import ConfigError, LoopConfig, load_config
from loop_harness.ledger import Ledger, Stage, TicketEntry, load_ledger, save_ledger

_DONE_STAGES = frozenset({Stage.COMMIT, Stage.DONE})
# Stages whose plan file is legitimately gone (done) or that never warrant a
# missing-plan warning (blocked): a reverse-orphan warning is scoped away from
# these, so the SessionStart briefing is not flooded with noise.
_NO_REVERSE_WARNING = frozenset({Stage.DONE, Stage.BLOCKED})


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


def resolve_plans_dir(repo: Path, config: LoopConfig) -> Path | None:
    """Resolve ``config.plans_dir`` to a repo-contained directory, or ``None``.

    Expands ``~`` and resolves a relative path against the repo root.
    Auto-registration must only consider plans UNDER the repo tree: a
    ``plans_dir`` that resolves OUTSIDE the repo (the shared-home default
    ``~/.claude/plans``) returns ``None``, so one repo's ledger never pulls
    another repo's plans into itself.

    Returns
    -------
    Path | None
        The resolved directory when it is the repo root or lives inside it;
        ``None`` when it resolves outside the repo.
    """
    raw = Path(config.plans_dir).expanduser()
    resolved = (raw if raw.is_absolute() else repo / raw).resolve()
    repo_root = repo.resolve()
    if resolved == repo_root or repo_root in resolved.parents:
        return resolved
    return None


def reconcile_plans(repo: Path, ledger: Ledger, config: LoopConfig) -> tuple[list[str], list[str]]:
    """Reconcile the ledger against the plan files on disk. Mutates ``ledger``.

    Forward (auto-register): a plan file under the repo-contained ``plans_dir``
    whose slug is absent from the ledger is registered at ``ready``, so a plan
    is never an invisible orphan. The trigger is the plan file's existence, not
    a creation event, so a missed registration is recovered on the next run.

    Reverse (warn, never delete): an entry whose plan file is missing yields a
    warning UNLESS it is terminal (``done``), ``blocked``, or ``dropped`` (whose
    plans are legitimately gone). The entry is never modified or removed.

    A ``dropped`` entry is left untouched in both directions: its surviving plan
    is not re-registered (that is why drop retires rather than deletes) and its
    missing plan does not warn.

    Returns
    -------
    tuple[list[str], list[str]]
        The slugs newly registered, and the reverse-orphan warning lines.
    """
    registered: list[str] = []
    warnings: list[str] = []
    plans_dir = resolve_plans_dir(repo, config)
    if plans_dir is None or not plans_dir.is_dir():
        return registered, warnings
    plan_slugs = {p.stem for p in plans_dir.glob("*.md")}
    for slug in sorted(plan_slugs):
        if slug not in ledger.entries:
            ledger.entries[slug] = TicketEntry(slug=slug)
            registered.append(slug)
    for entry in ledger.entries.values():
        if entry.dropped or entry.stage in _NO_REVERSE_WARNING:
            continue
        if entry.slug not in plan_slugs:
            warnings.append(
                f"{entry.slug}: registered at {entry.stage.value} but no plan file "
                f"under {config.plans_dir}"
            )
    return registered, warnings


def main() -> int:
    """CLI: reconcile the ledger against the plans on disk and against git.

    The plans pass runs before the git pass, so an orphan plan whose work is
    already committed is registered and then upgraded to ``done`` in one run.
    """
    repo = Path.cwd()
    ledger = load_ledger(repo)
    try:
        registered, warnings = reconcile_plans(repo, ledger, load_config(repo))
    except ConfigError:
        registered, warnings = [], []  # a broken config never blocks git reconcile
    corrections = reconcile(repo, ledger)
    if registered or corrections:
        save_ledger(repo, ledger)
    for slug in registered:
        print(f"{slug}: registered (ready) - orphan plan auto-registered")
    for c in corrections:
        print(f"{c.slug}: {c.before.value} -> {c.after.value} ({c.reason})")
    for w in warnings:
        print(f"warning: {w}")
    if not (registered or corrections or warnings):
        print("ledger consistent with git")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
