"""Git-level ``pre-commit`` backstop: a second, un-bypassable commit gate.

The Claude Code ``PreToolUse`` hook (``loop_harness.hooks``) can only see a
commit that surfaces as a matchable Bash tool string. A commit inside
``$(...)``, ``eval``, a language subprocess, or issued by a human at the
terminal never reaches it. This module installs a git ``pre-commit`` hook
that reuses the SAME ``decide_commit_gate`` policy, so git itself refuses a
commit that lacks earned evidence regardless of how it is spelled or who
issues it.

Fail direction (hard requirement): the entry fails OPEN on an internal error
(a harness bug, an unreadable file, an import failure), so the backstop can
never wedge a user's commits over a harness defect. Only a genuine policy
violation blocks. An engaged ``.loop/HALT`` steps the hook aside, and a repo
without ``.loop/`` no-ops (dormancy) — both mirroring the PreToolUse gate.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from loop_harness import halt as halt_mod
from loop_harness.hooks import (
    _ACTIVE_STAGES,
    decide_commit_gate,
    enabled_passes_failsafe,
    fingerprint_ignore_failsafe,
    loop_active,
    pass_verdict_tree,
)
from loop_harness.ledger import load_ledger
from loop_harness.stamp import tree_fingerprint, verify_stamp

# Marker line baked into every managed hook so install/uninstall can tell a
# harness-written hook from a consumer's own, without ever clobbering theirs.
MARKER = "loop-harness-managed pre-commit hook"


@dataclass(frozen=True)
class InstallResult:
    """Outcome of an install/uninstall action on the git hook.

    Attributes
    ----------
    ok : bool
        True when the end state is the intended one: the managed hook is in
        place (fresh or idempotent) for ``install``, or nothing managed
        remains for ``uninstall``. False only when ``install`` refused rather
        than clobber a consumer's own hook or ``core.hooksPath``.
    message : str
        Human-readable summary for the operator.
    """

    ok: bool
    message: str


def _hook_body(plugin_root: Path) -> str:
    """The managed ``pre-commit`` script text, with the plugin path baked in.

    A git hook runs with no ``${CLAUDE_PLUGIN_ROOT}``, so the absolute path to
    the plugin's stdlib shim is written in at install time. The shim locates
    ``loop_harness`` and fails open loudly on an import error, so a moved or
    reinstalled plugin never blocks a commit.

    Parameters
    ----------
    plugin_root :
        The plugin repository root (the ``run_git_hook.py`` shim lives under
        ``scripts/`` there).
    """
    shim = plugin_root / "scripts" / "run_git_hook.py"
    return (
        "#!/bin/sh\n"
        f"# {MARKER} — do not edit; remove with `loopctl uninstall-git-hook`\n"
        f'exec python3 "{shim}"\n'
    )


def _core_hooks_path(repo: Path) -> str | None:
    """The repo's configured ``core.hooksPath``, or ``None`` when unset.

    A set ``core.hooksPath`` disables the default ``.git/hooks`` directory
    wholesale, so writing a single ``.git/hooks/pre-commit`` would be silently
    inert — install refuses this case rather than mislead the operator.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value or None


def is_installed(repo: Path) -> bool:
    """Whether a harness-managed git ``pre-commit`` hook is present in ``repo``.

    Recognized by the marker, so a consumer's own unmanaged hook reads as not
    installed. Used by the SessionStart briefing to surface the install command
    only while the backstop is absent.
    """
    hook = repo / ".git" / "hooks" / "pre-commit"
    return hook.exists() and MARKER in hook.read_text(encoding="utf-8")


def install(repo: Path) -> InstallResult:
    """Install the managed git ``pre-commit`` backstop into ``repo``.

    Non-destructive (never clobbers a consumer's own ``pre-commit`` hook or a
    set ``core.hooksPath``) and idempotent (re-running over an already-managed
    hook rewrites it in place, never stacking a duplicate). The absolute
    plugin path the generated shim needs is baked in at write time.

    Parameters
    ----------
    repo :
        The consumer git repository to install the backstop into.

    Returns
    -------
    InstallResult
        ``ok=True`` when the managed hook is in place (fresh or idempotent);
        ``ok=False`` with a warning when an unmanaged hook or a set
        ``core.hooksPath`` made install refuse.
    """
    override = _core_hooks_path(repo)
    if override is not None:
        return InstallResult(
            ok=False,
            message=(
                f"refusing to install: core.hooksPath is set ({override}); "
                "it disables .git/hooks. Unset it or install the hook there manually."
            ),
        )
    hooks_dir = repo / ".git" / "hooks"
    hook = hooks_dir / "pre-commit"
    if hook.exists():
        existing = hook.read_text(encoding="utf-8")
        if MARKER not in existing:
            return InstallResult(
                ok=False,
                message=(
                    f"refusing to install: {hook} already exists and is not "
                    "harness-managed; the loop never clobbers an existing hook. "
                    "Remove or chain it manually, then re-run."
                ),
            )
    hooks_dir.mkdir(parents=True, exist_ok=True)
    plugin_root = Path(__file__).resolve().parents[2]
    hook.write_text(_hook_body(plugin_root), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return InstallResult(ok=True, message=f"installed managed git pre-commit hook: {hook}")


def uninstall(repo: Path) -> InstallResult:
    """Remove the managed git ``pre-commit`` hook from ``repo``.

    Removes ONLY a harness-managed hook (recognized by its marker). A no-op
    when no hook is present or the existing hook is a consumer's own unmanaged
    one — an unmanaged hook is never touched.

    Parameters
    ----------
    repo :
        The consumer git repository to remove the backstop from.

    Returns
    -------
    InstallResult
        Always ``ok=True``; the message states what was removed or that
        nothing managed was present.
    """
    hook = repo / ".git" / "hooks" / "pre-commit"
    if not hook.exists():
        return InstallResult(ok=True, message="no git pre-commit hook present (nothing to remove)")
    if MARKER not in hook.read_text(encoding="utf-8"):
        return InstallResult(
            ok=True,
            message=f"leaving unmanaged pre-commit hook untouched: {hook}",
        )
    hook.unlink()
    return InstallResult(ok=True, message=f"removed managed git pre-commit hook: {hook}")


def pre_commit() -> int:
    """Git ``pre-commit`` entry: gate the commit against the loop policy.

    Assembles the same evidence as the PreToolUse gate but keyed to the
    committed repo (git runs the hook with cwd at the working-tree root),
    reuses ``decide_commit_gate`` via a canonical ``"git commit"`` command,
    and translates the verdict to a git exit code.

    Returns
    -------
    int
        ``0`` to allow the commit (green evidence, an engaged HALT, a dormant
        repo, or an internal error failing OPEN); a non-zero code to block,
        with the reason on stderr.
    """
    try:
        repo = Path.cwd()
        if not loop_active(repo):
            return 0
        ledger = load_ledger(repo)
        active = [e for e in ledger.entries.values() if e.stage in _ACTIVE_STAGES]
        passes = enabled_passes_failsafe(repo)
        ignore = fingerprint_ignore_failsafe(repo)
        decision = decide_commit_gate(
            "git commit",
            halted=halt_mod.engaged(repo),
            verdict=verify_stamp(repo, ignore),
            active=active,
            pass_verdict_trees={
                e.slug: [(p.id, pass_verdict_tree(repo, e.slug, p)) for p in passes] for e in active
            },
            current_tree=tree_fingerprint(repo, ignore) if active else None,
        )
    except Exception as exc:  # fail OPEN: a hook bug must not wedge commits
        print(f"loop git-hook internal error (failing open): {exc}", file=sys.stderr)
        return 0
    if decision.allow:
        return 0
    print(decision.message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(pre_commit())
