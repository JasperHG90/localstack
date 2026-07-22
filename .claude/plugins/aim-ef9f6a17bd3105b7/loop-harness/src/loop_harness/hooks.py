"""Claude Code hook entry points: the layer that verifies stage claims.

Fail direction (hard requirement): internal errors fail OPEN, warn and
allow, so a hook bug never wedges commits or sessions. Only a genuine
policy violation blocks. An engaged HALT bypasses the commit gate: when
the loop is halted, the operator is in control.

Dormancy: a repo without a ``.loop/`` directory is not a loop consumer;
every hook no-ops there, so installing the plugin user-wide can never
gate commits or sessions in unrelated projects.

The commit gate enforces the lifecycle commit criterion at runtime via
``validate_transition``: while a ticket is mid-flight, a commit needs a
green stamp AND, for every ENABLED review pass, a passing verdict
(``.loop/verdicts/<slug>.<pass>.md``) whose recorded ``tree:`` fingerprint
equals the current tree. When review is deliberately disabled
(``require_review: false`` with no enabled pass), only the stamp is
required. A malformed config falls back to the mandatory adversarial pass,
never to zero (fail-safe, not fail-open). With no ticket mid-flight (an
operator commit), only the stamp is required.

Exit codes follow the Claude Code hook contract: 0 allows, 2 blocks
(with the reason on stderr).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from loop_harness import halt as halt_mod
from loop_harness.config import ConfigError, ReviewPass, load_config
from loop_harness.ledger import Stage, TicketEntry, load_ledger, save_ledger
from loop_harness.lifecycle import LifecycleError, validate_transition
from loop_harness.reconcile import reconcile as reconcile_git
from loop_harness.reconcile import reconcile_plans
from loop_harness.stamp import StampVerdict, tree_fingerprint, verify_stamp

# Raw-substring fallback for a `shlex` parse failure inside
# ``_invokes_git_commit`` (unbalanced quotes). The token-aware detector below
# is primary; this regex only backstops an unparseable segment.
_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")
# Shell sequencing operators that separate a compound command into segments.
# Split regardless of surrounding whitespace, so `git add&&git commit` still
# yields a `git commit` segment.
_SEQUENCING_RE = re.compile(r"&&|\|\||;|\||\n")
# Metacharacters in a path token the resolver cannot expand (variables, globs,
# home, subshells); their presence makes the commit target undeterminable.
_SHELL_META = frozenset("$`*?[]{}~()")
_TREE_RE = re.compile(r"tree:\s*([0-9a-f]{40})")
_PASS_RE = re.compile(r"^verdict:\s*(pass|pass-with-required-fixes)\s*$", re.MULTILINE)
_ACTIVE_STAGES = frozenset(
    {Stage.IMPLEMENTING, Stage.GATES, Stage.SELF_REVIEW, Stage.ADVERSARIAL_REVIEW, Stage.COMMIT}
)
_COMMITTABLE_STAGES = frozenset({Stage.ADVERSARIAL_REVIEW, Stage.COMMIT})
# awaiting a dispatched reviewer is a legitimate pause, not abandonment
_STOP_BLOCKING_STAGES = _ACTIVE_STAGES - {Stage.ADVERSARIAL_REVIEW}
# loop state only the harness may write; verdicts stay writable (the
# reviewer agent writes its own verdict file)
_GUARDED_STATE = frozenset({"ledger.json", "stamp.json"})

VERDICTS_DIR = Path(".loop") / "verdicts"


def _git_commit_c_path(tokens: list[str]) -> tuple[bool, str | None, bool]:
    """Inspect one command segment's ``tokens`` for a ``git commit`` invocation.

    Returns a triple ``(is_commit, c_path, determinable)``:

    - ``is_commit`` — the segment runs ``git`` with ``commit`` as its
      subcommand. A leading ``VAR=value`` assignment or a ``sudo``/``env``
      wrapper before ``git`` is skipped, and global options between ``git``
      and the subcommand (``-C``, ``-c``, other flags) are stepped over.
    - ``c_path`` — the value of a ``-C <path>`` global option that relocates
      the repository, or ``None`` for a commit in the current directory.
    - ``determinable`` — ``False`` when a global option this resolver does not
      model (``--git-dir``/``--work-tree``, or a ``-C`` path carrying shell
      metacharacters) leaves the target repo unknown, so the caller fails safe.

    Parameters
    ----------
    tokens :
        One command segment already split by ``shlex``.

    Returns
    -------
    tuple[bool, str | None, bool]
        The ``(is_commit, c_path, determinable)`` triple described above.
    """
    for i, tok in enumerate(tokens):
        if tok != "git":
            continue
        c_path: str | None = None
        determinable = True
        j = i + 1
        while j < len(tokens):
            opt = tokens[j]
            if opt == "-C" and j + 1 < len(tokens):
                c_path = tokens[j + 1]
                j += 2
                continue
            if opt == "-c" and j + 1 < len(tokens):
                j += 2  # a config override; it does not relocate the repo
                continue
            if opt.startswith(("--git-dir", "--work-tree")):
                determinable = False  # a repo-locating option this resolver skips
                j += 1 if "=" in opt else 2
                continue
            if opt.startswith("-"):
                j += 1  # any other global flag; assume it takes no value
                continue
            break  # the first non-option token is the subcommand
        if j < len(tokens) and tokens[j] == "commit":
            if c_path is not None and any(ch in _SHELL_META for ch in c_path):
                determinable = False
            return True, c_path, determinable
        # this `git` was not a commit; keep scanning for another `git` token
    return False, None, True


def _invokes_git_commit(command: str) -> bool:
    """Whether ``command`` actually invokes ``git commit`` as a subcommand.

    Fires on a genuine ``git commit`` invocation — including ``git -C <path>
    commit`` and a commit behind a leading ``VAR=value`` assignment or a
    ``sudo``/``env`` wrapper — but NOT on ``git commit`` appearing as string
    data (an ``echo`` argument, a ``--grep``/``-m`` value, or a comment),
    which a raw substring match mistook for a commit.

    The command is split on shell sequencing operators (``&&``, ``||``, ``;``,
    ``|``, newlines), so a commit inside a compound command is still seen.
    Each segment is tokenized with ``shlex`` and classified by
    ``_git_commit_c_path``. String data stays safe because ``shlex`` collapses
    a quoted ``"git commit"`` into ONE token, never a ``git`` token followed
    by a ``commit`` subcommand. A segment whose first non-blank character is
    ``#`` is a comment and is skipped. A segment ``shlex`` cannot parse
    (unbalanced quotes) falls back to the raw ``_GIT_COMMIT_RE`` substring
    match, so a malformed-but-committing command still gates (fail toward the
    gate).

    The boundary favors safety over precision: rare unquoted forms (``echo git
    commit``) over-gate rather than risk a miss, and constructs this does not
    model — subshells ``$(...)``, ``eval``, backgrounding, heredoc bodies, and
    operators inside quotes — are out of scope (ticket sections 5 and 11).

    Parameters
    ----------
    command :
        The Bash command under inspection.

    Returns
    -------
    bool
        True when a segment genuinely invokes ``git commit``.
    """
    for segment in _SEQUENCING_RE.split(command):
        stripped = segment.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            if _GIT_COMMIT_RE.search(segment):
                return True
            continue
        if _git_commit_c_path(tokens)[0]:
            return True
    return False


def _resolve_commit_repo(command: str, cwd: Path) -> Path | None:
    """The directory a ``git commit`` in ``command`` runs in, or ``None``.

    Resolves the two ways a commit lands somewhere other than ``cwd``: a
    leading ``cd <path> &&`` prefix (relative paths joined onto ``cwd``) and a
    ``git -C <path> commit`` form. A bare commit runs in ``cwd``. Returns
    ``None`` when the target cannot be pinned unambiguously — an unparseable
    segment, a ``cd`` this does not model (options, globs, no or many args), a
    path with shell metacharacters, or an out-of-scope ``--git-dir``/
    ``--work-tree`` option — so the caller can fail safe rather than gate the
    wrong repository.

    Parameters
    ----------
    command :
        The Bash command being committed.
    cwd :
        The session's working directory. The hook fires before any ``cd`` in
        the command runs, so ``cwd`` is where the command starts.

    Returns
    -------
    Path | None
        The resolved target directory, or ``None`` when undeterminable.
    """
    effective = cwd
    for segment in _SEQUENCING_RE.split(command):
        stripped = segment.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            return None
        if not tokens:
            continue
        if tokens[0] == "cd":
            if len(tokens) != 2 or any(ch in _SHELL_META for ch in tokens[1]):
                return None
            effective = Path(os.path.normpath(effective / tokens[1]))
            continue
        is_commit, c_path, determinable = _git_commit_c_path(tokens)
        if not is_commit:
            continue
        if not determinable:
            return None
        if c_path is not None:
            return Path(os.path.normpath(effective / c_path))
        return effective
    return None


def loop_active(repo: Path) -> bool:
    """Whether this repo uses the loop at all (``.loop/`` exists).

    The dormancy switch: in a repo that never opted in, the hooks must
    inject nothing and block nothing.
    """
    return (repo / ".loop").is_dir()


@dataclass(frozen=True)
class GateDecision:
    """Outcome of the commit-gate policy: allow or block, with a reason."""

    allow: bool
    message: str = ""


def _tree_from_verdict_file(path: Path) -> str | None:
    """Tree fingerprint of a PASSING verdict file, or ``None``.

    Returns the ``tree:`` value only when the file also carries
    ``verdict: pass`` or ``verdict: pass-with-required-fixes``. A failing,
    tree-less, or absent file yields ``None``, so it can never authorize a
    commit.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if not _PASS_RE.search(text):
        return None
    match = _TREE_RE.search(text)
    return match.group(1) if match else None


def verdict_tree(repo: Path, slug: str) -> str | None:
    """Tree fingerprint of the legacy single-file verdict ``<slug>.md``, or ``None``.

    Predates review passes; retained as the ``adversarial`` pass's fallback
    path (the reviewer agent historically wrote this file).
    """
    return _tree_from_verdict_file(repo / VERDICTS_DIR / f"{slug}.md")


def pass_verdict_tree(repo: Path, slug: str, review_pass: ReviewPass) -> str | None:
    """Tree fingerprint bound by one review pass's passing verdict, or ``None``.

    Reads ``.loop/verdicts/<slug>.<pass-id>.md``. The ``adversarial`` pass
    additionally falls back to the legacy ``<slug>.md`` path, so a reviewer
    that still writes the old filename keeps authorizing commits.
    """
    tree = _tree_from_verdict_file(repo / VERDICTS_DIR / review_pass.verdict_filename(slug))
    if tree is None and review_pass.id == "adversarial":
        tree = verdict_tree(repo, slug)
    return tree


def decide_commit_gate(
    command: str,
    *,
    halted: str | None,
    verdict: StampVerdict,
    active: Sequence[TicketEntry] = (),
    pass_verdict_trees: Mapping[str, Sequence[tuple[str, str | None]]] | None = None,
    current_tree: str | None = None,
) -> GateDecision:
    """Pure policy: should this Bash command be allowed to commit?

    Parameters
    ----------
    command :
        The Bash command under review; only ``git commit`` is gated.
    halted :
        HALT reason when engaged; an engaged HALT bypasses the gate.
    verdict :
        Current stamp verdict for the tree.
    active :
        Ledger entries currently mid-flight (loop commit when non-empty).
    pass_verdict_trees :
        Per-slug sequence of ``(pass_id, tree)`` pairs, one per enabled
        review pass. Every pair must match ``current_tree``; an empty
        sequence for a slug means review is disabled and the stamp alone
        gates its commit.
    current_tree :
        Fingerprint of the tree being committed.

    Returns
    -------
    GateDecision
        ``allow`` plus a human-readable reason for the transcript.
    """
    if not _invokes_git_commit(command):
        return GateDecision(allow=True)
    if halted is not None:
        return GateDecision(
            allow=True,
            message=f"loop gate bypassed: HALT engaged ({halted}); operator is in control",
        )
    if not verdict.ok:
        return GateDecision(
            allow=False,
            message=(
                f"loop gate: commit blocked - stamp {verdict.status.value}"
                f"{': ' + verdict.detail if verdict.detail else ''}"
            ),
        )
    for entry in active:
        if entry.stage not in _COMMITTABLE_STAGES:
            return GateDecision(
                allow=False,
                message=(
                    f"loop gate: ticket {entry.slug} is at stage {entry.stage.value}; "
                    "commits happen only from the review stage with tree-bound verdicts"
                ),
            )
        try:
            validate_transition(
                Stage.ADVERSARIAL_REVIEW,
                Stage.COMMIT,
                stamp=verdict,
                pass_verdict_trees=(pass_verdict_trees or {}).get(entry.slug, ()),
                current_tree=current_tree,
            )
        except LifecycleError as exc:
            return GateDecision(allow=False, message=f"loop gate: {entry.slug}: {exc}")
    suffix = "; verdicts bound" if active else ""
    return GateDecision(allow=True, message=f"loop gate: stamp ok{suffix}")


def enabled_passes_failsafe(repo: Path) -> tuple[ReviewPass, ...]:
    """Enabled review passes, or the mandatory adversarial pass on a broken config.

    The commit gate must never fall OPEN on a malformed config: that would
    silently drop all review. A ``ConfigError`` here yields the single
    adversarial pass, so a commit still needs an adversarial verdict. A VALID
    config that opts out of review (``require_review: false``) returns its
    real, possibly empty, set — the only path to a stamp-only commit.
    """
    try:
        return load_config(repo).enabled_review_passes()
    except ConfigError:
        return (ReviewPass(id="adversarial", agent="loop-reviewer"),)


def fingerprint_ignore_failsafe(repo: Path) -> tuple[str, ...]:
    """The configured fingerprint ignore-list, or the STRICT empty list on a
    broken config.

    A ``ConfigError`` must never RELAX the fingerprint: falling back to ``()``
    keeps the whole-tree guarantee (more staling, never less), so a malformed
    config cannot let a real code change slip past the commit gate unhashed.
    """
    try:
        return load_config(repo).fingerprint_ignore
    except ConfigError:
        return ()


def _pre_commit_gate() -> int:
    """PreToolUse entry: gate ``git commit`` Bash commands; fail open."""
    try:
        payload = json.load(sys.stdin)
        command = str(payload.get("tool_input", {}).get("command", ""))
        if not _invokes_git_commit(command):
            return 0
        cwd = Path.cwd()
        repo = _resolve_commit_repo(command, cwd)
        if repo is None:
            # Undeterminable target: fail SAFE (block) only when the session
            # cwd is itself a loop consumer and not halted. Otherwise there is
            # no gated repo to protect, so step aside (dormant cwd or an
            # engaged HALT means the operator is in control).
            if loop_active(cwd) and halt_mod.engaged(cwd) is None:
                print(
                    "loop gate: cannot determine the commit's target repo from "
                    f"{command!r}; run a bare `git commit` in the target repo, "
                    "or engage HALT",
                    file=sys.stderr,
                )
                return 2
            return 0
        if not loop_active(repo):
            return 0
        ledger = load_ledger(repo)
        active = [e for e in ledger.entries.values() if e.stage in _ACTIVE_STAGES]
        passes = enabled_passes_failsafe(repo)
        ignore = fingerprint_ignore_failsafe(repo)
        decision = decide_commit_gate(
            command,
            halted=halt_mod.engaged(repo),
            verdict=verify_stamp(repo, ignore),
            active=active,
            pass_verdict_trees={
                e.slug: [(p.id, pass_verdict_tree(repo, e.slug, p)) for p in passes] for e in active
            },
            current_tree=tree_fingerprint(repo, ignore) if active else None,
        )
    except Exception as exc:  # fail OPEN: a hook bug must not wedge commits
        print(f"loop gate internal error (failing open): {exc}", file=sys.stderr)
        return 0
    if decision.allow:
        if decision.message:
            print(decision.message)
        return 0
    print(decision.message, file=sys.stderr)
    return 2


def _session_start() -> int:
    """SessionStart entry: inject ledger and HALT state as context."""
    try:
        repo = Path.cwd()
        if not loop_active(repo):
            return 0
        ledger = load_ledger(repo)
        # Reconcile plans <-> ledger and git so an orphan plan registers and
        # surfaces here every session (R8), and a self-healed orphan whose work
        # is already committed lands `done` in the one pass (plans before git).
        registered: list[str] = []
        warnings: list[str] = []
        with contextlib.suppress(ConfigError):  # a broken config never blocks reconcile
            registered, warnings = reconcile_plans(repo, ledger, load_config(repo))
        corrections = reconcile_git(repo, ledger)
        if registered or corrections:
            save_ledger(repo, ledger)
        lines = ["[loop] ledger:"]
        if not ledger.entries:
            lines.append("  (empty - no tickets registered)")
        for entry in ledger.entries.values():
            blocker = (
                f" [{entry.blocker.code.value}: {entry.blocker.reason}]" if entry.blocker else ""
            )
            dropped = " [dropped]" if entry.dropped else ""
            lines.append(f"  {entry.slug}: {entry.stage.value}{blocker}{dropped}")
        for slug in registered:
            lines.append(f"  (auto-registered orphan plan: {slug})")
        for w in warnings:
            lines.append(f"  warning: {w}")
        reason = halt_mod.engaged(repo)
        lines.append(f"[loop] HALT: {'ENGAGED - ' + reason if reason else 'clear'}")
        with contextlib.suppress(Exception):  # best-effort discoverability hint (G1)
            from loop_harness import githook

            if not githook.is_installed(repo):
                lines.append(
                    "[loop] git-hook backstop not installed: run "
                    "`loopctl install-git-hook` for an un-bypassable commit gate"
                )
        try:
            if not load_config(repo).enabled_review_passes():
                lines.append(
                    "[loop] review DISABLED: commits gated by the stamp alone "
                    "(require_review:false)"
                )
        except ConfigError as exc:
            lines.append(
                f"[loop] config ERROR ({exc}); commit gate falls back to the adversarial pass"
            )
        ctl_path = Path(__file__).resolve().parents[2] / "scripts" / "loopctl.py"
        lines.append(f'[loop] ctl: python3 "{ctl_path}"')
        print("\n".join(lines))
    except Exception as exc:  # context injection is best-effort
        print(f"[loop] session-start error (non-fatal): {exc}")
    return 0


def decide_state_guard(file_path: str) -> GateDecision:
    """Pure policy: may an Edit/Write touch this path?

    ``.loop/ledger.json`` and ``.loop/stamp.json`` are written only by
    the harness (``loop_harness.ctl`` / ``just stamp``); direct edits are
    how stage discipline erodes.
    """
    path = Path(file_path)
    if ".loop" in path.parts and path.name in _GUARDED_STATE:
        return GateDecision(
            allow=False,
            message=(
                f"loop state {path.name} is harness-written only: "
                "use loopctl (register/advance/block/done/stamp)"
            ),
        )
    return GateDecision(allow=True)


def _state_guard() -> int:
    """PreToolUse entry for Edit/Write: guard loop state files; fail open."""
    try:
        if not loop_active(Path.cwd()):
            return 0
        payload = json.load(sys.stdin)
        file_path = str(payload.get("tool_input", {}).get("file_path", ""))
        if not file_path:
            return 0
        decision = decide_state_guard(file_path)
    except Exception as exc:  # fail OPEN: a hook bug must not wedge edits
        print(f"loop state-guard internal error (failing open): {exc}", file=sys.stderr)
        return 0
    if decision.allow:
        return 0
    print(decision.message, file=sys.stderr)
    return 2


def _stop_check() -> int:
    """Stop entry: block stopping only when a ticket is mid-flight with
    uncommitted work and no HALT; fail open on internal errors.

    ``adversarial-review`` does not block: a dispatched reviewer resolves
    asynchronously and stopping while it runs is legitimate."""
    try:
        repo = Path.cwd()
        if not loop_active(repo):
            return 0
        if halt_mod.engaged(repo) is not None:
            return 0
        ledger = load_ledger(repo)
        active = [e for e in ledger.entries.values() if e.stage in _STOP_BLOCKING_STAGES]
        if not active:
            return 0
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not dirty:
            return 0
        slugs = ", ".join(e.slug for e in active)
        print(
            f"loop: ticket(s) mid-flight ({slugs}) with uncommitted changes. "
            "Finish the lifecycle (commit via the gate), set the ledger stage to "
            "blocked with a reason code, or engage HALT before stopping.",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # fail OPEN: never wedge a session
        print(f"loop stop-check internal error (failing open): {exc}", file=sys.stderr)
        return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch a hook entry point by name."""
    parser = argparse.ArgumentParser(description="loop hook entry points")
    parser.add_argument(
        "hook", choices=["session-start", "pre-commit-gate", "stop-check", "state-guard"]
    )
    args = parser.parse_args(argv)
    if args.hook == "session-start":
        return _session_start()
    if args.hook == "pre-commit-gate":
        return _pre_commit_gate()
    if args.hook == "state-guard":
        return _state_guard()
    return _stop_check()


if __name__ == "__main__":
    raise SystemExit(main())
