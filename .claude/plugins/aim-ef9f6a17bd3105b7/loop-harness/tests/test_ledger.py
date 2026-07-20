"""Ledger: round-trip, defaults, atomic save."""

from __future__ import annotations

from pathlib import Path

from loop_harness.ledger import (
    Blocker,
    BlockerCode,
    Ledger,
    Stage,
    TicketEntry,
    load_ledger,
    save_ledger,
)


def test_load_missing_ledger_is_empty(tmp_path: Path) -> None:
    """Load missing ledger is empty."""
    assert load_ledger(tmp_path).entries == {}


def test_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    """Roundtrip preserves all fields."""
    ledger = Ledger(
        entries={
            "some-ticket": TicketEntry(
                slug="some-ticket",
                stage=Stage.BLOCKED,
                attempts=2,
                review_cycles=1,
                blocker=Blocker(
                    code=BlockerCode.UNRESOLVED_DESIGN_FORK,
                    reason="DECISIONS.md has no answer for the storage fork",
                ),
                commit_sha=None,
                review_verdict=".loop/verdicts/some-ticket.md",
            ),
            "other-ticket": TicketEntry(slug="other-ticket"),
        }
    )
    save_ledger(tmp_path, ledger)
    loaded = load_ledger(tmp_path)
    assert loaded == ledger


def test_save_creates_parent_and_is_readable(tmp_path: Path) -> None:
    """Save creates parent and is readable."""
    save_ledger(tmp_path, Ledger(entries={"t": TicketEntry(slug="t")}))
    assert (tmp_path / ".loop" / "ledger.json").exists()
    assert load_ledger(tmp_path).entries["t"].stage is Stage.READY


def test_save_leaves_no_tmp_droppings(tmp_path: Path) -> None:
    """Save leaves no tmp droppings."""
    save_ledger(tmp_path, Ledger())
    leftovers = [p for p in (tmp_path / ".loop").iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
