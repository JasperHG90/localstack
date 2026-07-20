"""Evidence stamp: proof that the gates ran, and on which exact tree.

``loopctl stamp`` executes the consumer's configured gate commands and
writes the stamp; the commit hook and the lifecycle entry criteria verify
it. "Gates passed" is a verifiable artifact bound to a tree fingerprint,
never a claim.

The tree fingerprint is defined ONCE here (``tree_fingerprint``); every
reader calls this function. Two definitions would let the gate pass in one
place and block in another.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from loop_harness.config import LoopConfig

STAMP_FILE = Path(".loop") / "stamp.json"


class StampStatus(StrEnum):
    """Verify outcome for the evidence stamp."""

    OK = "ok"
    MISSING = "missing"  # no stamp written yet
    INVALID = "invalid"  # unreadable or malformed
    STALE = "stale"  # tree changed since the gates ran
    RED = "red"  # gates ran and failed


@dataclass(frozen=True)
class StampVerdict:
    """Result of verifying the stamp against the current tree."""

    status: StampStatus
    detail: str = ""

    @property
    def ok(self) -> bool:
        """Whether the gates ran green on the exact current tree."""
        return self.status is StampStatus.OK


@dataclass(frozen=True)
class GateResult:
    """One executed gate command and its exit code."""

    command: str
    exit_code: int


def tree_fingerprint(repo: Path) -> str:
    """Hash of the full working tree (tracked + untracked, .gitignore
    respected): ``git write-tree`` over a throwaway index built with
    ``git add -A``.

    ``.loop/`` is excluded: the stamp certifies the CODE tree, so loop
    state (the stamp itself, ledger updates, HALT) never invalidates it.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))

        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", *args],
                cwd=repo,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout

        git("add", "-A", ".")
        git("rm", "-r", "--cached", "--ignore-unmatch", "-q", ".loop")
        return git("write-tree").strip()


def run_gates(repo: Path, config: LoopConfig) -> list[GateResult]:
    """Execute every configured gate command and record its exit code.

    All gates run even after a failure, so the stamp records the full
    picture. Output streams to the caller's terminal (the operator and
    the agent read it there).

    Raises
    ------
    ValueError
        When no gates are configured — an empty gate list must never
        produce a green stamp (author ``.loop/config.json`` first).
    """
    if not config.gates:
        raise ValueError(
            "no gates configured: author .loop/config.json (run `loopctl init` "
            "for a starter) before stamping"
        )
    results: list[GateResult] = []
    for command in config.gates:
        proc = subprocess.run(command, shell=True, cwd=repo, check=False)
        results.append(GateResult(command=command, exit_code=proc.returncode))
    return results


def write_stamp(
    repo: Path,
    results: list[GateResult],
    *,
    now: dt.datetime | None = None,
) -> Path:
    """Run-independent record: write tree fingerprint + per-gate exits."""
    at = now if now is not None else dt.datetime.now(dt.UTC)
    payload = {
        "tree": tree_fingerprint(repo),
        "gates": [{"command": r.command, "exit": r.exit_code} for r in results],
        "at": at.isoformat(),
    }
    path = repo / STAMP_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def verify_stamp(repo: Path) -> StampVerdict:
    """Judge the stamp against the current tree; see ``StampStatus``."""
    path = repo / STAMP_FILE
    if not path.exists():
        return StampVerdict(StampStatus.MISSING, "no stamp: run `loopctl stamp`")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        tree = str(payload["tree"])
        gates = [
            GateResult(command=str(g["command"]), exit_code=int(g["exit"]))
            for g in payload["gates"]
        ]
        if not gates:
            raise ValueError("stamp records no gates")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return StampVerdict(StampStatus.INVALID, f"unreadable stamp: {exc}")
    failed = [g for g in gates if g.exit_code != 0]
    if failed:
        detail = ", ".join(f"{g.command!r}={g.exit_code}" for g in failed)
        return StampVerdict(StampStatus.RED, f"gates failed ({detail})")
    if tree != tree_fingerprint(repo):
        return StampVerdict(
            StampStatus.STALE,
            "tree changed since the gates ran: re-run `loopctl stamp`",
        )
    return StampVerdict(StampStatus.OK)


def main(argv: list[str] | None = None) -> int:
    """CLI: verify the evidence stamp (writing goes through ``loopctl stamp``)."""
    parser = argparse.ArgumentParser(description="loop evidence stamp")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    parser.parse_args(argv)
    verdict = verify_stamp(Path.cwd())
    print(f"{verdict.status.value}: {verdict.detail}" if verdict.detail else verdict.status.value)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
