"""Gate-failure history: the repo remembers red stamps, not the agent.

``.loop/stamp.json`` is a latest-only snapshot: a ticket that goes RED, RED,
then GREEN leaves only the final green stamp on disk, so the count of red gate
runs over a ticket's life used to survive only in the agent's memory, which is
why the reflection asked the agent for it. This module records every red stamp
as one append-only event under ``.loop/history/<slug>.jsonl``, so ``distill``
can derive ``gates_red`` from evidence instead of a self-report.

The log is churny per-gate-run state, so it lives under ``.loop/`` and stays
out of the tree fingerprint (which binds only ``.loop/config.json``); a history
write late in the lifecycle never stales a green stamp.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from loop_harness.stamp import GateResult

HISTORY_DIR = Path(".loop") / "history"


def append_gate_failure(
    repo: Path,
    slug: str,
    failed: list[GateResult],
    tree: str,
    *,
    now: dt.datetime | None = None,
) -> Path:
    """Append one red-stamp event to ``.loop/history/<slug>.jsonl``.

    Append-only: N red runs leave N lines, so the count of red gate runs over a
    ticket's life is recoverable as evidence. One JSON object per line records
    the slug, the timestamp, the failing gate commands with their exit codes,
    and the tree fingerprint the gates ran on.

    Parameters
    ----------
    repo :
        Repository root.
    slug :
        Ticket the failing gates belong to.
    failed :
        The gate commands that exited non-zero (``[r for r in results if
        r.exit_code != 0]``).
    tree :
        The tree fingerprint the gates ran on.
    now :
        Timestamp to record; defaults to the current UTC time.

    Returns
    -------
    Path
        The per-slug history log the event was appended to.
    """
    at = now if now is not None else dt.datetime.now(dt.UTC)
    event = {
        "slug": slug,
        "at": at.isoformat(),
        "tree": tree,
        "failed_gates": [{"command": r.command, "exit": r.exit_code} for r in failed],
    }
    path = repo / HISTORY_DIR / f"{slug}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")
    return path


def read_gate_failures(repo: Path, slug: str) -> list[dict[str, object]]:
    """Return the recorded red-stamp events for ``slug``, oldest first.

    Parameters
    ----------
    repo :
        Repository root.
    slug :
        Ticket whose history to read.

    Returns
    -------
    list[dict[str, object]]
        One decoded event per recorded red stamp; an empty list when no log
        exists. Blank lines are skipped.
    """
    path = repo / HISTORY_DIR / f"{slug}.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def count_gate_failures(repo: Path, slug: str) -> int:
    """Return the number of recorded red-stamp events for ``slug``."""
    return len(read_gate_failures(repo, slug))
