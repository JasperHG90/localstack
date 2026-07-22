"""Stamp: tree fingerprint semantics and verify outcomes."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_history_log_never_stales_the_stamp(repo: Path) -> None:
    """The gate-failure history is churny ``.loop`` state: writing
    ``.loop/history/<slug>.jsonl`` after a green stamp keeps it OK, because the
    fingerprint binds only ``.loop/config.json``."""
    write_stamp(repo, [GateResult("pytest", 0)])
    history = repo / ".loop" / "history"
    history.mkdir(parents=True, exist_ok=True)
    (history / "some-ticket.jsonl").write_text(
        '{"slug": "some-ticket", "failed_gates": []}\n', encoding="utf-8"
    )
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


def test_fingerprint_ignores_configured_paths(repo: Path) -> None:
    """A configured ignore pattern removes matching untracked files from the
    fingerprint, so generated-artifact churn no longer stales the stamp."""
    ignore = ("docs/assets/",)
    before = tree_fingerprint(repo, ignore)
    (repo / "docs" / "assets").mkdir(parents=True)
    (repo / "docs" / "assets" / "new.png").write_text("png", encoding="utf-8")
    assert tree_fingerprint(repo, ignore) == before


def test_ignore_list_never_hides_a_real_source_change(repo: Path) -> None:
    """The load-bearing guarantee: with an ignore-list set, a change to any
    NON-ignored file still changes the fingerprint, so real code cannot commit
    ungated. This is the hole the rejected inclusion-list alternative reopens."""
    ignore = ("docs/assets/",)
    before = tree_fingerprint(repo, ignore)
    (repo / "module.py").write_text("x = 1\n", encoding="utf-8")
    assert tree_fingerprint(repo, ignore) != before


def test_absent_ignore_list_is_backward_compatible(repo: Path) -> None:
    """With no ignore-list (the default), a file that a list WOULD ignore still
    changes the fingerprint: today's whole-tree behavior is preserved."""
    before = tree_fingerprint(repo)
    (repo / "docs" / "assets").mkdir(parents=True)
    (repo / "docs" / "assets" / "new.png").write_text("png", encoding="utf-8")
    assert tree_fingerprint(repo) != before


def test_ignore_pattern_uses_git_pathspec_not_gitignore(repo: Path) -> None:
    """git pathspec semantics, not .gitignore: ``*.lock`` matches paths ENDING
    in .lock, so ``aim.lock.toml`` is NOT ignored and still stales the stamp.
    A mis-authored pattern under-ignores; the fail-safe is it never
    over-ignores real source."""
    ignore = ("*.lock",)
    before = tree_fingerprint(repo, ignore)
    (repo / "aim.lock.toml").write_text("lock\n", encoding="utf-8")
    assert tree_fingerprint(repo, ignore) != before


def test_verify_ok_when_only_ignored_file_added_after_stamp(repo: Path) -> None:
    """Roundtrip: a stamp taken with an ignore-list still verifies OK after an
    ignored file lands (the inverse of the stale-on-tree-move test)."""
    ignore = ("docs/assets/",)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)], ignore=ignore)
    (repo / "docs" / "assets").mkdir(parents=True)
    (repo / "docs" / "assets" / "new.png").write_text("png", encoding="utf-8")
    assert verify_stamp(repo, ignore).status is StampStatus.OK


def test_verify_stale_when_non_ignored_file_moves_despite_ignore_list(repo: Path) -> None:
    """Guardrail through verify: an ignore-list does not weaken staleness for
    real code. Editing a non-ignored file after the stamp still reads STALE."""
    ignore = ("docs/assets/",)
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)], ignore=ignore)
    (repo / "README.md").write_text("moved\n", encoding="utf-8")
    assert verify_stamp(repo, ignore).status is StampStatus.STALE


def test_all_callers_fingerprint_identically_via_config(repo: Path) -> None:
    """Every caller resolves the same ignore-list from config, so write and
    verify fingerprint byte-identically: an ignored file added between them
    does not read STALE (no caller drift breaking the single definition)."""
    import json

    from loop_harness.config import CONFIG_FILE, load_config

    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps({"gates": ["true"], "fingerprint_ignore": ["docs/assets/"]}),
        encoding="utf-8",
    )
    write_stamp(repo, [GateResult("true", 0)], ignore=load_config(repo).fingerprint_ignore)
    (repo / "docs" / "assets").mkdir(parents=True)
    (repo / "docs" / "assets" / "x.png").write_text("p", encoding="utf-8")
    assert verify_stamp(repo, load_config(repo).fingerprint_ignore).status is StampStatus.OK


def test_config_edit_stales_the_stamp(repo: Path) -> None:
    """Reproducer: the verification contract (``.loop/config.json``) is bound
    into the fingerprint, so weakening a gate stales a previously green stamp."""
    import json

    from loop_harness.config import CONFIG_FILE, load_config

    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"gates": ["uv run pytest"]}), encoding="utf-8")
    ignore = load_config(repo).fingerprint_ignore
    write_stamp(repo, [GateResult("uv run pytest", 0)], ignore=ignore)
    assert verify_stamp(repo, ignore).status is StampStatus.OK

    # Weaken the gate: the contract changed, so the stamp must go STALE.
    cfg.write_text(json.dumps({"gates": ["uv run pytest || true"]}), encoding="utf-8")
    assert verify_stamp(repo, load_config(repo).fingerprint_ignore).status is StampStatus.STALE


@pytest.mark.parametrize("ignore_pattern", [".loop/config.json", ".loop/", ".loop"])
def test_fingerprint_ignore_cannot_exclude_config(repo: Path, ignore_pattern: str) -> None:
    """R4 guardrail: an adversarial ``fingerprint_ignore`` naming config.json (or
    a broad ``.loop`` pathspec) cannot un-bind the contract. The re-bind runs
    AFTER the ignore loop, so editing config still stales the stamp."""
    import json

    from loop_harness.config import CONFIG_FILE, load_config

    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps({"gates": ["uv run pytest"], "fingerprint_ignore": [ignore_pattern]}),
        encoding="utf-8",
    )
    ignore = load_config(repo).fingerprint_ignore
    write_stamp(repo, [GateResult("uv run pytest", 0)], ignore=ignore)
    assert verify_stamp(repo, ignore).status is StampStatus.OK

    cfg.write_text(
        json.dumps({"gates": ["uv run pytest || true"], "fingerprint_ignore": [ignore_pattern]}),
        encoding="utf-8",
    )
    assert verify_stamp(repo, load_config(repo).fingerprint_ignore).status is StampStatus.STALE


def test_churny_loop_state_still_never_stales_with_config_bound(repo: Path) -> None:
    """R2: binding config.json does not bind the rest of ``.loop/``. With config
    present and unchanged, writing the ledger, HALT, a reflection, and a handoff
    log (standing in for the sibling ticket's history log) keeps a green stamp
    OK."""
    import json

    from loop_harness.config import CONFIG_FILE, load_config

    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"gates": ["true"]}), encoding="utf-8")
    ignore = load_config(repo).fingerprint_ignore
    write_stamp(repo, [GateResult("true", 0)], ignore=ignore)

    (repo / ".loop" / "ledger.json").write_text('{"entries": {}}\n', encoding="utf-8")
    (repo / ".loop" / "HALT").write_text("paused\n", encoding="utf-8")
    (repo / ".loop" / "reflections").mkdir(parents=True, exist_ok=True)
    (repo / ".loop" / "reflections" / "x.md").write_text("reflection\n", encoding="utf-8")
    (repo / ".loop" / "handoff.log").write_text("log\n", encoding="utf-8")
    assert verify_stamp(repo, ignore).status is StampStatus.OK


def test_config_binding_backward_compatible_when_absent(repo: Path) -> None:
    """R5 fail-safe: with no ``.loop/config.json`` the fingerprint behaves exactly
    as before (no crash), and a real code change still stales the stamp."""
    assert not (repo / ".loop" / "config.json").exists()
    write_stamp(repo, [GateResult("pytest", 0)])
    assert verify_stamp(repo).status is StampStatus.OK

    # A churny .loop file still does not stale.
    (repo / ".loop" / "ledger.json").write_text("{}\n", encoding="utf-8")
    assert verify_stamp(repo).status is StampStatus.OK

    # A real code change still stales.
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    assert verify_stamp(repo).status is StampStatus.STALE
