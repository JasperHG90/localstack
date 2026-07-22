"""``loopctl``: the single blessed CLI over every harness operation.

One entry point replaces the authoring repo's justfile recipes: gates and
evidence (``stamp``, ``verify``), state (``ledger``, ``reconcile``),
transitions (``register``, ``advance``, ``block``, ``done``, ``finish``),
the kill switch (``halt``, ``resume``, ``status``), and consumer
bootstrap (``init``). Consumers may wrap these in their own task runner;
the CLI is the contract.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from loop_harness import ctl, githook, halt, hooks, reconcile
from loop_harness import stamp as stamp_mod
from loop_harness.config import ConfigError, LoopConfig, load_config, write_example_config
from loop_harness.evals import verify_eval
from loop_harness.history import append_gate_failure
from loop_harness.ledger import BlockerCode, Stage, load_ledger
from loop_harness.reflection import (
    REFLECTIONS_DIR,
    distill,
    format_distill,
    scaffold_reflection,
    verify_reflection,
)
from loop_harness.stamp import (
    GateResult,
    StampStatus,
    run_gates,
    tree_fingerprint,
    verify_stamp,
    write_stamp,
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def cmd_stamp(repo: Path) -> int:
    """Run the configured gates, write the evidence stamp, verify it.

    On a RED verdict the failing gates are recorded to the active ticket's
    gate-failure history (``.loop/history/<slug>.jsonl``) so ``distill`` can
    derive ``gates_red`` from evidence. Recording is best-effort: a broken
    history write degrades to a warning and never turns a gate result into a
    crash.
    """
    config = load_config(repo)
    results = run_gates(repo, config)
    path = write_stamp(repo, results, ignore=config.fingerprint_ignore)
    print(f"stamp written: {path}")
    verdict = verify_stamp(repo, config.fingerprint_ignore)
    print(f"{verdict.status.value}: {verdict.detail}" if verdict.detail else verdict.status.value)
    if verdict.status is StampStatus.RED:
        _record_gate_failure(repo, results, config)
    return 0 if verdict.ok else 1


def _active_slug(repo: Path) -> str | None:
    """Return the slug of the one ticket in an active stage, else ``None``.

    The gate-failure history is per-ticket, so a red stamp is attributed to the
    single active ticket. When the loop is idle or ambiguous (no active ticket,
    or more than one), the failure is left unrecorded rather than misattributed.
    """
    active = [e for e in load_ledger(repo).entries.values() if e.stage in hooks._ACTIVE_STAGES]
    return active[0].slug if len(active) == 1 else None


def _record_gate_failure(repo: Path, results: list[GateResult], config: LoopConfig) -> None:
    """Append the failing gates to the active ticket's history, never raising.

    Resolves the active ticket from the ledger and records the red stamp; any
    error (no active ticket, an unwritable log) is swallowed so a broken history
    write cannot abort stamping.
    """
    try:
        slug = _active_slug(repo)
        if slug is None:
            return
        failed = [r for r in results if r.exit_code != 0]
        tree = tree_fingerprint(repo, config.fingerprint_ignore)
        append_gate_failure(repo, slug, failed, tree)
    except Exception as exc:
        print(f"warning: could not record gate failure: {exc}", file=sys.stderr)


def cmd_finish(repo: Path, slug: str) -> int:
    """Close a ticket and fold the ledger update into its commit.

    Guards (both hard): HEAD must be the slug-anchored commit, and the
    index must hold no staged content — the amend may fold ONLY the
    ledger update into the reviewed commit.
    """
    head_subject = _git(repo, "log", "-1", "--format=%s").strip()
    if not head_subject.startswith(f"{slug}:"):
        print(f"finish: HEAD is not the '{slug}' commit", file=sys.stderr)
        return 1
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--ita-invisible-in-index"],
        cwd=repo,
        check=False,
    )
    if staged.returncode != 0:
        print("finish: index has staged content; commit or unstage it first", file=sys.stderr)
        return 1
    print(ctl.done(repo, slug))
    _git(repo, "add", ".loop/ledger.json", str(REFLECTIONS_DIR / f"{slug}.md"))
    _git(repo, "commit", "--amend", "--no-edit", "-q")
    reconcile.main()
    print(f"folded ledger update into: {_git(repo, 'log', '--oneline', '-1').strip()}")
    return 0


def cmd_reflect(repo: Path, slug: str) -> int:
    """Scaffold the reflection when absent, otherwise validate the existing one.

    The first call writes a schema-valid template for the author to fill; a
    later call re-validates it and reports the verdict.
    """
    path = repo / REFLECTIONS_DIR / f"{slug}.md"
    if not path.exists():
        scaffold_reflection(repo, slug)
        print(f"scaffolded {path} - fill in friction/worked, then re-run to validate")
        return 0
    verdict = verify_reflection(repo, slug)
    print(f"{verdict.status.value}: {verdict.detail}" if verdict.detail else verdict.status.value)
    return 0 if verdict.ok else 1


def cmd_eval(repo: Path, slug: str) -> int:
    """Verify a ticket's eval marker against the schema and report the verdict.

    Check-only by design: unlike ``reflect``, this never scaffolds a template.
    The interactive ``create-eval`` skill authors the marker; a stub scaffold
    here would undercut the forcing function that skill exists to provide.
    """
    verdict = verify_eval(repo, slug)
    print(f"{verdict.status.value}: {verdict.detail}" if verdict.detail else verdict.status.value)
    return 0 if verdict.ok else 1


def cmd_distill(repo: Path) -> int:
    """Aggregate the reflections and print the ticket-planner briefing."""
    print(format_distill(distill(repo)))
    return 0


def cmd_install_git_hook(repo: Path) -> int:
    """Install the git ``pre-commit`` backstop into this repo (explicit, per G1).

    Prints the outcome and returns 0 when the managed hook is in place, or 1
    when install refused rather than clobber a consumer's own hook or a set
    ``core.hooksPath``.
    """
    result = githook.install(repo)
    print(result.message, file=sys.stdout if result.ok else sys.stderr)
    return 0 if result.ok else 1


def cmd_uninstall_git_hook(repo: Path) -> int:
    """Remove the managed git ``pre-commit`` backstop; a no-op when absent."""
    result = githook.uninstall(repo)
    print(result.message)
    return 0


def cmd_init(repo: Path) -> int:
    """Scaffold ``.loop/config.json`` for a new consumer repo."""
    try:
        path = write_example_config(repo)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"wrote {path} - edit the gate commands to this repo's blessed invocations")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch a loopctl subcommand."""
    parser = argparse.ArgumentParser(prog="loopctl", description="loop harness control")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="scaffold .loop/config.json")
    sub.add_parser("install-git-hook", help="install the git pre-commit backstop")
    sub.add_parser("uninstall-git-hook", help="remove the managed git pre-commit backstop")
    sub.add_parser("stamp", help="run configured gates + write evidence stamp")
    sub.add_parser("verify", help="verify the stamp against the current tree")
    sub.add_parser("reconcile", help="correct the ledger from git")
    sub.add_parser("ledger", help="show ledger + HALT state")
    reg = sub.add_parser("register", help="register a ticket (stage: ready)")
    reg.add_argument("slug")
    adv = sub.add_parser("advance", help="validated stage transition")
    adv.add_argument("slug")
    adv.add_argument(
        "stage", choices=[s.value for s in Stage if s not in (Stage.BLOCKED, Stage.DONE)]
    )
    blk = sub.add_parser("block", help="block a ticket with a coded reason")
    blk.add_argument("slug")
    blk.add_argument("code", choices=[c.value for c in BlockerCode])
    blk.add_argument("reason")
    dn = sub.add_parser("done", help="close a ticket (slug-anchored commit required)")
    dn.add_argument("slug")
    drp = sub.add_parser("drop", help="retire a ticket, reversibly (register to restore)")
    drp.add_argument("slug")
    fin = sub.add_parser("finish", help="done + fold ledger into the ticket commit")
    fin.add_argument("slug")
    rfl = sub.add_parser("reflect", help="scaffold or validate a ticket reflection")
    rfl.add_argument("slug")
    evl = sub.add_parser("eval", help="verify a ticket's eval marker (check-only)")
    evl.add_argument("slug")
    sub.add_parser("distill", help="aggregate reflections for the ticket-planner")
    hlt = sub.add_parser("halt", help="engage the loop kill switch")
    hlt.add_argument("reason", nargs="?", default="manual halt")
    sub.add_parser("resume", help="clear the loop kill switch")
    sub.add_parser("status", help="show the kill-switch state")
    args = parser.parse_args(argv)
    repo = Path.cwd()

    if args.cmd == "init":
        return cmd_init(repo)
    if args.cmd == "install-git-hook":
        return cmd_install_git_hook(repo)
    if args.cmd == "uninstall-git-hook":
        return cmd_uninstall_git_hook(repo)
    if args.cmd == "stamp":
        return cmd_stamp(repo)
    if args.cmd == "verify":
        return stamp_mod.main(["verify"])
    if args.cmd == "reconcile":
        return reconcile.main()
    if args.cmd == "ledger":
        return hooks.main(["session-start"])
    if args.cmd == "register":
        print(ctl.register(repo, args.slug))
        return 0
    if args.cmd == "advance":
        print(ctl.advance(repo, args.slug, Stage(args.stage)))
        return 0
    if args.cmd == "block":
        print(ctl.block(repo, args.slug, BlockerCode(args.code), args.reason))
        return 0
    if args.cmd == "done":
        print(ctl.done(repo, args.slug))
        return 0
    if args.cmd == "drop":
        print(ctl.drop(repo, args.slug))
        return 0
    if args.cmd == "finish":
        return cmd_finish(repo, args.slug)
    if args.cmd == "reflect":
        return cmd_reflect(repo, args.slug)
    if args.cmd == "eval":
        return cmd_eval(repo, args.slug)
    if args.cmd == "distill":
        return cmd_distill(repo)
    if args.cmd == "halt":
        return halt.main(["engage", str(args.reason)])
    if args.cmd == "resume":
        return halt.main(["clear"])
    return halt.main(["status"])


if __name__ == "__main__":
    raise SystemExit(main())
