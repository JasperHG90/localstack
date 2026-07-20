"""Hooks: the pure commit-gate policy, including the runtime verdict gate."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

from loop_harness import hooks
from loop_harness.config import CONFIG_FILE, ReviewPass
from loop_harness.hooks import (
    VERDICTS_DIR,
    decide_commit_gate,
    enabled_passes_failsafe,
    pass_verdict_tree,
    verdict_tree,
)
from loop_harness.ledger import Stage, TicketEntry
from loop_harness.stamp import StampStatus, StampVerdict

OK = StampVerdict(StampStatus.OK)
MISSING = StampVerdict(StampStatus.MISSING, "no stamp: run `just stamp`")
STALE = StampVerdict(StampStatus.STALE)
RED = StampVerdict(StampStatus.RED)
TREE = "a" * 40
SLUG = "some-ticket"


@pytest.mark.parametrize(
    "command",
    ["ls -la", "git status", "git log --oneline", "uv run pytest", "git commitish"],
)
def test_non_commit_commands_pass_untouched(command: str) -> None:
    """Only `git commit` is gated; everything else passes silently."""
    decision = decide_commit_gate(command, halted=None, verdict=MISSING)
    assert decision.allow
    assert decision.message == ""


@pytest.mark.parametrize(
    "command",
    ["git commit -m 'x'", "git add -A && git commit -m 'y'", "cd /repo && git commit"],
)
def test_commit_without_stamp_is_blocked(command: str) -> None:
    """No stamp means no commit, in plain and compound commands."""
    decision = decide_commit_gate(command, halted=None, verdict=MISSING)
    assert not decision.allow
    assert "missing" in decision.message


@pytest.mark.parametrize("verdict", [STALE, RED])
def test_commit_with_bad_stamp_is_blocked(verdict: StampVerdict) -> None:
    """A stale or red stamp blocks the commit."""
    assert not decide_commit_gate("git commit", halted=None, verdict=verdict).allow


def test_operator_commit_with_green_stamp_is_allowed() -> None:
    """With no ticket mid-flight, a green stamp is the only requirement."""
    assert decide_commit_gate("git commit -m 'ok'", halted=None, verdict=OK).allow


def test_halt_bypasses_the_gate() -> None:
    """An engaged HALT means the operator is in control: allow."""
    decision = decide_commit_gate("git commit", halted="operator halt", verdict=MISSING)
    assert decision.allow
    assert "HALT" in decision.message


def _entry(stage: Stage) -> TicketEntry:
    """Build a mid-flight ledger entry at the given stage."""
    return TicketEntry(slug=SLUG, stage=stage)


def test_loop_commit_requires_tree_bound_verdict() -> None:
    """A mid-flight ticket commits only with a verdict bound to this tree."""
    decision = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(Stage.ADVERSARIAL_REVIEW)],
        pass_verdict_trees={SLUG: [("adversarial", TREE)]},
        current_tree=TREE,
    )
    assert decision.allow
    assert "verdicts bound" in decision.message


def test_loop_commit_without_verdict_is_blocked() -> None:
    """Green stamp alone is not enough while a ticket is mid-flight."""
    decision = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(Stage.ADVERSARIAL_REVIEW)],
        pass_verdict_trees={SLUG: [("adversarial", None)]},
        current_tree=TREE,
    )
    assert not decision.allow
    assert "verdict" in decision.message


def test_loop_commit_with_mismatched_verdict_tree_is_blocked() -> None:
    """A verdict for a different tree does not authorize this commit."""
    decision = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(Stage.ADVERSARIAL_REVIEW)],
        pass_verdict_trees={SLUG: [("adversarial", "b" * 40)]},
        current_tree=TREE,
    )
    assert not decision.allow


def test_loop_commit_needs_every_enabled_pass_bound() -> None:
    """With multiple passes, one absent or stale verdict blocks the commit."""
    both_bound = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(Stage.ADVERSARIAL_REVIEW)],
        pass_verdict_trees={SLUG: [("adversarial", TREE), ("architectural", TREE)]},
        current_tree=TREE,
    )
    assert both_bound.allow
    one_missing = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(Stage.ADVERSARIAL_REVIEW)],
        pass_verdict_trees={SLUG: [("adversarial", TREE), ("architectural", None)]},
        current_tree=TREE,
    )
    assert not one_missing.allow
    assert "architectural" in one_missing.message


def test_loop_commit_with_no_passes_is_stamp_only() -> None:
    """A deliberate opt-out (empty passes) gates a mid-flight commit on the stamp alone."""
    decision = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(Stage.ADVERSARIAL_REVIEW)],
        pass_verdict_trees={SLUG: []},
        current_tree=TREE,
    )
    assert decision.allow


@pytest.mark.parametrize("stage", [Stage.IMPLEMENTING, Stage.GATES, Stage.SELF_REVIEW])
def test_loop_commit_from_pre_review_stage_is_blocked(stage: Stage) -> None:
    """Commits happen only from adversarial-review (or commit) stages."""
    decision = decide_commit_gate(
        "git commit",
        halted=None,
        verdict=OK,
        active=[_entry(stage)],
        pass_verdict_trees={SLUG: [("adversarial", TREE)]},
        current_tree=TREE,
    )
    assert not decision.allow
    assert stage.value in decision.message


def test_awaiting_review_does_not_block_stopping() -> None:
    """A dispatched reviewer resolves asynchronously: stopping is legitimate."""
    from loop_harness.hooks import _ACTIVE_STAGES, _STOP_BLOCKING_STAGES

    assert Stage.ADVERSARIAL_REVIEW in _ACTIVE_STAGES  # still commit-gated
    assert Stage.ADVERSARIAL_REVIEW not in _STOP_BLOCKING_STAGES
    assert {Stage.IMPLEMENTING, Stage.GATES, Stage.SELF_REVIEW, Stage.COMMIT} <= (
        _STOP_BLOCKING_STAGES
    )


@pytest.mark.parametrize(
    "path",
    [".loop/ledger.json", "/abs/repo/.loop/ledger.json", ".loop/stamp.json"],
)
def test_state_guard_blocks_harness_state(path: str) -> None:
    """Direct Edit/Write on harness state is refused."""
    from loop_harness.hooks import decide_state_guard

    decision = decide_state_guard(path)
    assert not decision.allow
    assert "harness-written" in decision.message


@pytest.mark.parametrize(
    "path",
    [
        ".loop/verdicts/some-ticket.md",
        ".loop/reflections/some-ticket.md",
        ".loop/HALT",
        "src/trailstop/core/rails.py",
        "ledger.json",
    ],
)
def test_state_guard_allows_everything_else(path: str) -> None:
    """Verdicts, reflections (both agent-written), HALT, and ordinary files stay writable."""
    from loop_harness.hooks import decide_state_guard

    assert decide_state_guard(path).allow


def test_verdict_tree_requires_a_passing_verdict_line(tmp_path: Path) -> None:
    """Only a PASSING verdict yields its tree; fail/absent yields None."""
    assert verdict_tree(tmp_path, SLUG) is None
    path = tmp_path / VERDICTS_DIR / f"{SLUG}.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"tree: {TREE}\n", encoding="utf-8")
    assert verdict_tree(tmp_path, SLUG) is None  # no verdict line at all
    path.write_text(f"verdict: fail\ntree: {TREE}\n", encoding="utf-8")
    assert verdict_tree(tmp_path, SLUG) is None  # a FAIL never authorizes
    path.write_text("verdict: pass\n", encoding="utf-8")
    assert verdict_tree(tmp_path, SLUG) is None  # pass without a tree binds nothing
    path.write_text(f"verdict: pass-with-required-fixes\ntree: {TREE}\n", encoding="utf-8")
    assert verdict_tree(tmp_path, SLUG) == TREE
    path.write_text(f"verdict: pass\ntree: {TREE}\n", encoding="utf-8")
    assert verdict_tree(tmp_path, SLUG) == TREE


def test_hooks_are_dormant_without_loop_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo that never opted into the loop is never gated or narrated:
    installing the plugin user-wide must not block commits elsewhere."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    assert hooks.loop_active(tmp_path) is False
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_input": {"command": "git commit -m x"}}))
    )
    assert hooks.main(["pre-commit-gate"]) == 0
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": ".loop/ledger.json"}}))
    )
    assert hooks.main(["state-guard"]) == 0
    assert hooks.main(["stop-check"]) == 0
    assert hooks.main(["session-start"]) == 0


def test_pass_verdict_tree_namespaced_with_adversarial_legacy_fallback(tmp_path: Path) -> None:
    """A pass reads its ``<slug>.<id>.md`` file; adversarial falls back to ``<slug>.md``."""
    adversarial = ReviewPass(id="adversarial", agent="loop-reviewer")
    architectural = ReviewPass(id="architectural", agent="loop-architect")
    vdir = tmp_path / VERDICTS_DIR
    vdir.mkdir(parents=True)
    (vdir / f"{SLUG}.architectural.md").write_text(
        f"verdict: pass\ntree: {TREE}\n", encoding="utf-8"
    )
    assert pass_verdict_tree(tmp_path, SLUG, architectural) == TREE
    # adversarial has no namespaced file yet, and no legacy file either
    assert pass_verdict_tree(tmp_path, SLUG, adversarial) is None
    (vdir / f"{SLUG}.md").write_text(f"verdict: pass\ntree: {TREE}\n", encoding="utf-8")
    assert pass_verdict_tree(tmp_path, SLUG, adversarial) == TREE  # legacy fallback
    # a non-adversarial pass does NOT inherit the legacy file
    assert pass_verdict_tree(tmp_path, SLUG, ReviewPass(id="documentation", agent="x")) is None


def test_enabled_passes_failsafe_never_falls_to_zero_on_broken_config(repo: Path) -> None:
    """A malformed config yields the mandatory adversarial pass, never an empty set."""
    cfg = repo / CONFIG_FILE
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("{broken", encoding="utf-8")
    assert [p.id for p in enabled_passes_failsafe(repo)] == ["adversarial"]
    # a VALID explicit opt-out is the only path to an empty (stamp-only) set
    cfg.write_text(
        json.dumps({"gates": ["true"], "require_review": False, "review_passes": []}),
        encoding="utf-8",
    )
    assert enabled_passes_failsafe(repo) == ()


def test_pre_commit_gate_fails_safe_on_broken_config(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken config must BLOCK an unreviewed commit, not fall open to allow it."""
    from loop_harness.ledger import Ledger, save_ledger
    from loop_harness.stamp import GateResult, write_stamp

    (repo / ".loop").mkdir(exist_ok=True)
    save_ledger(
        repo, Ledger(entries={SLUG: TicketEntry(slug=SLUG, stage=Stage.ADVERSARIAL_REVIEW)})
    )
    write_stamp(repo, [GateResult("pytest", 0), GateResult("prek", 0)])  # green, bound to tree
    (repo / CONFIG_FILE).write_text("{broken", encoding="utf-8")  # malformed
    # no verdict file exists, so the fallback adversarial pass has nothing to bind
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_input": {"command": "git commit -m x"}}))
    )
    assert hooks.main(["pre-commit-gate"]) == 2  # blocked, NOT failed-open to 0


def test_session_start_warns_when_review_is_disabled(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A valid require_review:false opt-out surfaces a loud line at session start."""
    from loop_harness.ledger import Ledger, save_ledger

    (repo / ".loop").mkdir(exist_ok=True)
    save_ledger(repo, Ledger(entries={}))
    (repo / CONFIG_FILE).write_text(
        json.dumps({"gates": ["true"], "require_review": False, "review_passes": []}),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    assert hooks.main(["session-start"]) == 0
    assert "review DISABLED" in capsys.readouterr().out


def test_session_start_flags_broken_config_but_still_prints_ledger(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed config is surfaced, yet the ledger still prints (nested guard)."""
    from loop_harness.ledger import Ledger, save_ledger

    (repo / ".loop").mkdir(exist_ok=True)
    save_ledger(repo, Ledger(entries={}))
    (repo / CONFIG_FILE).write_text("{broken", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert hooks.main(["session-start"]) == 0
    out = capsys.readouterr().out
    assert "config ERROR" in out
    assert "[loop] ledger:" in out  # the bad config must not blank the ledger display
