"""Stamp: tree fingerprint semantics and verify outcomes."""

from __future__ import annotations

from pathlib import Path

from loop_harness.stamp import (
    STAMP_FILE,
    GateResult,
    StampStatus,
    tree_fingerprint,
    verify_stamp,
    write_stamp,
)


def test_fingerprint_is_stable_on_unchanged_tree(repo: Path) -> None:
    """Fingerprint is stable on unchanged tree."""
    assert tree_fingerprint(repo) == tree_fingerprint(repo)


def test_fingerprint_changes_when_tracked_file_changes(repo: Path) -> None:
    """Fingerprint changes when tracked file changes."""
    before = tree_fingerprint(repo)
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    assert tree_fingerprint(repo) != before


def test_fingerprint_sees_untracked_files(repo: Path) -> None:
    """Fingerprint sees untracked files."""
    before = tree_fingerprint(repo)
    (repo / "new_module.py").write_text("x = 1\n", encoding="utf-8")
    assert tree_fingerprint(repo) != before


def test_fingerprint_respects_gitignore(repo: Path) -> None:
    """Fingerprint respects gitignore."""
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    before = tree_fingerprint(repo)
    (repo / "ignored.txt").write_text("noise\n", encoding="utf-8")
    assert tree_fingerprint(repo) == before


def test_verify_missing(repo: Path) -> None:
    """Verify missing."""
    assert verify_stamp(repo).status is StampStatus.MISSING


def test_verify_ok_roundtrip(repo: Path) -> None:
    """Verify ok roundtrip."""
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    verdict = verify_stamp(repo)
    assert verdict.status is StampStatus.OK
    assert verdict.ok


def test_verify_red_when_gates_failed(repo: Path) -> None:
    """Verify red when gates failed."""
    write_stamp(repo, [GateResult("pytest", 1), GateResult("prek", 0)])
    assert verify_stamp(repo).status is StampStatus.RED


def test_verify_stale_when_tree_moves_after_stamp(repo: Path) -> None:
    """Verify stale when tree moves after stamp."""
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    (repo / "README.md").write_text("moved on\n", encoding="utf-8")
    assert verify_stamp(repo).status is StampStatus.STALE


def test_verify_invalid_on_corrupt_stamp(repo: Path) -> None:
    """Verify invalid on corrupt stamp."""
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    (repo / STAMP_FILE).write_text("not json", encoding="utf-8")
    assert verify_stamp(repo).status is StampStatus.INVALID


def test_loop_state_never_invalidates_the_stamp(repo: Path) -> None:
    """The stamp certifies the CODE tree: writing the stamp itself, updating
    the ledger, or engaging HALT must not flip a green stamp to STALE."""
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])
    (repo / ".loop" / "ledger.json").write_text('{"entries": {}}\n', encoding="utf-8")
    (repo / ".loop" / "HALT").write_text("paused\n", encoding="utf-8")
    assert verify_stamp(repo).status is StampStatus.OK


def test_hand_written_empty_gates_stamp_is_never_green(repo: Path) -> None:
    """The K2 loophole: a hand-written stamp recording ZERO gates must not
    verify green — deleting the guard would let an agent fake evidence."""
    import datetime as dt
    import json

    stamp_path = repo / STAMP_FILE
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(
            {
                "tree": tree_fingerprint(repo),
                "gates": [],
                "at": dt.datetime.now(dt.UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    verdict = verify_stamp(repo)
    assert verdict.ok is False
    assert verdict.status is StampStatus.INVALID
