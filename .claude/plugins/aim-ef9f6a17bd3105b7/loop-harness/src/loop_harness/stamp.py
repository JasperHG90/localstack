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

from loop_harness.config import CONFIG_FILE, LoopConfig, load_config

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


def tree_fingerprint(repo: Path, ignore: tuple[str, ...] = ()) -> str:
    """Hash of the full working tree (tracked + untracked, .gitignore
    respected): ``git write-tree`` over a throwaway index built with
    ``git add -A``.

    ``.loop/`` is excluded so loop bookkeeping (the stamp itself, ledger
    updates, HALT) never invalidates a code stamp — EXCEPT
    ``.loop/config.json``, which is re-bound into the hash. That file
    defines the verification contract (the gate commands and this ``ignore``
    list), so a change to it must stale the stamp and force a re-stamp and
    re-review. The re-bind runs AFTER the ``.loop`` strip and the ``ignore``
    loop, so no ignore pattern can un-bind the contract; a missing
    config.json is non-fatal (the tree is the whole working set minus
    ``.loop``, exactly as before).

    Each ``ignore`` entry is an additional exclusion applied the same way,
    so a consumer's generated working-tree files (logo assets, install
    lockfiles) stop staling an otherwise-unchanged stamp. It only ever
    REMOVES the matched paths from the hash: a change to any file NOT
    matched by a pattern still changes the fingerprint. Scope patterns to
    generated paths only — an over-broad pathspec (e.g. ``.`` or ``src``)
    shadows real source, so a change under it would NOT stale the stamp
    and could commit ungated. The harness cannot tell a generated path
    from source, so honest patterns are the operator's responsibility.

    Parameters
    ----------
    repo :
        Repository root to fingerprint.
    ignore :
        git pathspecs (NOT ``.gitignore`` globs; ``*`` crosses directory
        boundaries, so ``*.lock`` matches paths ending in ``.lock`` but not
        ``aim.lock.toml``) to subtract from the hashed tree. Every caller
        must pass the SAME list, resolved from ``LoopConfig.fingerprint_ignore``,
        or write and verify would fingerprint differently.

    Returns
    -------
    str
        The ``git write-tree`` object id for the certified code tree.
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
        for pattern in ignore:
            # ``--`` guards a pattern that looks like an option from being
            # parsed as one; ``--ignore-unmatch`` makes a no-match a no-op.
            git("rm", "-r", "--cached", "--ignore-unmatch", "-q", "--", pattern)
        # Re-bind the verification contract LAST, after the strip and the
        # ignore loop, so neither can un-bind it. ``-f`` binds config even if a
        # consumer gitignores ``.loop/``; the existence guard keeps a missing
        # config non-fatal (a fatal ``git`` here would be swallowed by the
        # commit hook's fail-open and silently disable the gate).
        if (repo / CONFIG_FILE).exists():
            git("add", "-f", "--", CONFIG_FILE.as_posix())
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
    ignore: tuple[str, ...] = (),
    now: dt.datetime | None = None,
) -> Path:
    """Run-independent record: write tree fingerprint + per-gate exits.

    Parameters
    ----------
    repo :
        Repository root to stamp.
    results :
        Executed gate commands and their exit codes.
    ignore :
        Fingerprint ignore-list (``LoopConfig.fingerprint_ignore``) passed
        through to ``tree_fingerprint``; ``verify_stamp`` must be given the
        same list or the stamp reads STALE.
    now :
        Timestamp to record; defaults to the current UTC time.
    """
    at = now if now is not None else dt.datetime.now(dt.UTC)
    payload = {
        "tree": tree_fingerprint(repo, ignore),
        "gates": [{"command": r.command, "exit": r.exit_code} for r in results],
        "at": at.isoformat(),
    }
    path = repo / STAMP_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def verify_stamp(repo: Path, ignore: tuple[str, ...] = ()) -> StampVerdict:
    """Judge the stamp against the current tree; see ``StampStatus``.

    ``ignore`` (``LoopConfig.fingerprint_ignore``) must match the list
    ``write_stamp`` used, so verify hashes the same certified code tree;
    a mismatched list would flip a green stamp to STALE.
    """
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
    if tree != tree_fingerprint(repo, ignore):
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
    repo = Path.cwd()
    verdict = verify_stamp(repo, load_config(repo).fingerprint_ignore)
    print(f"{verdict.status.value}: {verdict.detail}" if verdict.detail else verdict.status.value)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
