"""Halt file semantics and handoff records."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from loop_harness.halt import HALT_FILE, HANDOFF_FILE, clear, engage, engaged, handoff


def test_not_engaged_by_default(tmp_path: Path) -> None:
    """Not engaged by default."""
    assert engaged(tmp_path) is None


def test_engage_and_clear_roundtrip(tmp_path: Path) -> None:
    """Engage and clear roundtrip."""
    engage(tmp_path, "drawdown breach")
    assert engaged(tmp_path) == "drawdown breach"
    clear(tmp_path)
    assert engaged(tmp_path) is None


def test_empty_halt_file_still_halts(tmp_path: Path) -> None:
    """Empty halt file still halts."""
    path = tmp_path / HALT_FILE
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    assert engaged(tmp_path) == "halted"


def test_handoff_appends_timestamped_lines(tmp_path: Path) -> None:
    """Handoff appends timestamped lines."""
    at = dt.datetime(2026, 7, 2, 12, 0, tzinfo=dt.UTC)
    handoff(tmp_path, "ticket-a: blocked (unresolved-design-fork)", now=at)
    handoff(tmp_path, "ticket-a: unblocked by operator", now=at)
    lines = (tmp_path / HANDOFF_FILE).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("2026-07-02T12:00:00+00:00\t")
