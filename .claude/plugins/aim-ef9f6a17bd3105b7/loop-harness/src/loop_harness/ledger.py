"""Ticket ledger: the loop's durable per-ticket state (``.loop/ledger.json``).

Git is ground truth for commits; the ledger holds only what git cannot:
stage, attempts, review cycles, blockers. ``reconcile`` corrects the ledger
from git, never the reverse. The ledger file is committed (attempt and
blocker history are ledger-only truth).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

LEDGER_FILE = Path(".loop") / "ledger.json"


class Stage(StrEnum):
    """Lifecycle stage of a ticket in the loop."""

    READY = "ready"
    IMPLEMENTING = "implementing"
    GATES = "gates"
    SELF_REVIEW = "self-review"
    ADVERSARIAL_REVIEW = "adversarial-review"
    COMMIT = "commit"
    DONE = "done"
    BLOCKED = "blocked"


class BlockerCode(StrEnum):
    """Failure taxonomy: why a ticket is blocked."""

    UNRESOLVED_DESIGN_FORK = "unresolved-design-fork"
    OUT_OF_SCOPE_FIX_NEEDED = "out-of-scope-fix-needed"
    GATE_FLAKE = "gate-flake"
    DISPUTED_REVIEWER_FINDING = "disputed-reviewer-finding"
    ENVIRONMENT_BREAKAGE = "environment-breakage"
    CAP_EXCEEDED = "cap-exceeded"


@dataclass
class Blocker:
    """A blocked ticket's reason, coded for the operator."""

    code: BlockerCode
    reason: str


@dataclass
class TicketEntry:
    """Per-ticket loop state that git cannot record."""

    slug: str
    stage: Stage = Stage.READY
    attempts: int = 0
    review_cycles: int = 0
    blocker: Blocker | None = None
    commit_sha: str | None = None
    review_verdict: str | None = None  # path to the reviewer-verdict file

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry to a JSON-compatible dict."""
        return {
            "slug": self.slug,
            "stage": self.stage.value,
            "attempts": self.attempts,
            "review_cycles": self.review_cycles,
            "blocker": (
                {"code": self.blocker.code.value, "reason": self.blocker.reason}
                if self.blocker is not None
                else None
            ),
            "commit_sha": self.commit_sha,
            "review_verdict": self.review_verdict,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TicketEntry:
        """Build an entry from its JSON dict, tolerating absent fields."""
        blocker_raw = raw.get("blocker")
        blocker = (
            Blocker(code=BlockerCode(blocker_raw["code"]), reason=str(blocker_raw["reason"]))
            if isinstance(blocker_raw, dict)
            else None
        )
        return cls(
            slug=str(raw["slug"]),
            stage=Stage(raw.get("stage", Stage.READY.value)),
            attempts=int(raw.get("attempts", 0)),
            review_cycles=int(raw.get("review_cycles", 0)),
            blocker=blocker,
            commit_sha=raw.get("commit_sha"),
            review_verdict=raw.get("review_verdict"),
        )


@dataclass
class Ledger:
    """All ticket entries, keyed by slug."""

    entries: dict[str, TicketEntry] = field(default_factory=dict)


def load_ledger(repo: Path) -> Ledger:
    """Read the ledger from disk; a missing file is an empty ledger."""
    path = repo / LEDGER_FILE
    if not path.exists():
        return Ledger()
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = {slug: TicketEntry.from_dict(entry) for slug, entry in raw.get("entries", {}).items()}
    return Ledger(entries=entries)


def save_ledger(repo: Path, ledger: Ledger) -> None:
    """Atomic write (tmp + rename): a crash mid-save never corrupts state."""
    path = repo / LEDGER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": {slug: e.to_dict() for slug, e in ledger.entries.items()}}
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
