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

from loop_harness import ctl, halt, hooks, reconcile
from loop_harness import stamp as stamp_mod
from loop_harness.config import ConfigError, load_config, write_example_config
from loop_harness.ledger import BlockerCode, Stage
from loop_harness.reflection import (
    REFLECTIONS_DIR,
    distill,
    format_distill,
    scaffold_reflection,
    verify_reflection,
)
from loop_harness.stamp import run_gates, verify_stamp, write_stamp


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def cmd_stamp(repo: Path) -> int:
    """Run the configured gates, write the evidence stamp, verify it."""
    results = run_gates(repo, load_config(repo))
    path = write_stamp(repo, results)
    print(f"stamp written: {path}")
    verdict = verify_stamp(repo)
    print(f"{verdict.status.value}: {verdict.detail}" if verdict.detail else verdict.status.value)
    return 0 if verdict.ok else 1


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


def cmd_distill(repo: Path) -> int:
    """Aggregate the reflections and print the ticket-planner briefing."""
    print(format_distill(distill(repo)))
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
    fin = sub.add_parser("finish", help="done + fold ledger into the ticket commit")
    fin.add_argument("slug")
    rfl = sub.add_parser("reflect", help="scaffold or validate a ticket reflection")
    rfl.add_argument("slug")
    sub.add_parser("distill", help="aggregate reflections for the ticket-planner")
    hlt = sub.add_parser("halt", help="engage the loop kill switch")
    hlt.add_argument("reason", nargs="?", default="manual halt")
    sub.add_parser("resume", help="clear the loop kill switch")
    sub.add_parser("status", help="show the kill-switch state")
    args = parser.parse_args(argv)
    repo = Path.cwd()

    if args.cmd == "init":
        return cmd_init(repo)
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
    if args.cmd == "finish":
        return cmd_finish(repo, args.slug)
    if args.cmd == "reflect":
        return cmd_reflect(repo, args.slug)
    if args.cmd == "distill":
        return cmd_distill(repo)
    if args.cmd == "halt":
        return halt.main(["engage", str(args.reason)])
    if args.cmd == "resume":
        return halt.main(["clear"])
    return halt.main(["status"])


if __name__ == "__main__":
    raise SystemExit(main())
