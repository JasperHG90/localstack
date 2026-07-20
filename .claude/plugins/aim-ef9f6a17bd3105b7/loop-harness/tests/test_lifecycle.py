"""Lifecycle: mechanical entry criteria, findings loop cap, blocked rules."""

from __future__ import annotations

import pytest

from loop_harness.ledger import Stage
from loop_harness.lifecycle import LifecycleError, validate_transition
from loop_harness.stamp import StampStatus, StampVerdict

OK = StampVerdict(StampStatus.OK)
RED = StampVerdict(StampStatus.RED)
STALE = StampVerdict(StampStatus.STALE)
MISSING = StampVerdict(StampStatus.MISSING)


def test_ready_to_implementing_needs_nothing() -> None:
    """Ready to implementing needs nothing."""
    validate_transition(Stage.READY, Stage.IMPLEMENTING)


@pytest.mark.parametrize("stamp", [OK, RED])
def test_gates_entry_accepts_fresh_stamp(stamp: StampVerdict) -> None:
    """Gates entry accepts fresh stamp."""
    validate_transition(Stage.IMPLEMENTING, Stage.GATES, stamp=stamp)


@pytest.mark.parametrize("stamp", [None, STALE, MISSING])
def test_gates_entry_rejects_unfresh_stamp(stamp: StampVerdict | None) -> None:
    """Gates entry rejects unfresh stamp."""
    with pytest.raises(LifecycleError):
        validate_transition(Stage.IMPLEMENTING, Stage.GATES, stamp=stamp)


@pytest.mark.parametrize("stamp", [RED, STALE, MISSING, None])
def test_self_review_entry_requires_green(stamp: StampVerdict | None) -> None:
    """Self review entry requires green."""
    with pytest.raises(LifecycleError):
        validate_transition(Stage.GATES, Stage.SELF_REVIEW, stamp=stamp)


def test_adversarial_review_entry_requires_green() -> None:
    """Adversarial review entry requires green."""
    validate_transition(Stage.SELF_REVIEW, Stage.ADVERSARIAL_REVIEW, stamp=OK)
    with pytest.raises(LifecycleError):
        validate_transition(Stage.SELF_REVIEW, Stage.ADVERSARIAL_REVIEW, stamp=RED)


def test_commit_entry_requires_single_verdict_bound_to_current_tree() -> None:
    """N=1 reproduces the legacy single-verdict commit criterion exactly."""
    validate_transition(
        Stage.ADVERSARIAL_REVIEW,
        Stage.COMMIT,
        stamp=OK,
        pass_verdict_trees=[("adversarial", "abc123")],
        current_tree="abc123",
    )
    with pytest.raises(LifecycleError):
        validate_transition(
            Stage.ADVERSARIAL_REVIEW,
            Stage.COMMIT,
            stamp=OK,
            pass_verdict_trees=[("adversarial", "abc123")],
            current_tree="def456",
        )
    with pytest.raises(LifecycleError):
        validate_transition(
            Stage.ADVERSARIAL_REVIEW,
            Stage.COMMIT,
            stamp=OK,
            pass_verdict_trees=[("adversarial", None)],
            current_tree="abc123",
        )


def test_commit_requires_every_enabled_pass_bound_to_current_tree() -> None:
    """With N passes, commit needs all of them bound; one stale/absent blocks."""
    validate_transition(
        Stage.ADVERSARIAL_REVIEW,
        Stage.COMMIT,
        stamp=OK,
        pass_verdict_trees=[("adversarial", "abc123"), ("architectural", "abc123")],
        current_tree="abc123",
    )
    with pytest.raises(LifecycleError, match="architectural"):
        validate_transition(
            Stage.ADVERSARIAL_REVIEW,
            Stage.COMMIT,
            stamp=OK,
            pass_verdict_trees=[("adversarial", "abc123"), ("architectural", "def456")],
            current_tree="abc123",
        )
    with pytest.raises(LifecycleError, match="documentation"):
        validate_transition(
            Stage.ADVERSARIAL_REVIEW,
            Stage.COMMIT,
            stamp=OK,
            pass_verdict_trees=[("adversarial", "abc123"), ("documentation", None)],
            current_tree="abc123",
        )


def test_commit_with_no_passes_needs_only_a_green_stamp() -> None:
    """Review disabled (empty passes): a green stamp alone authorizes commit."""
    validate_transition(
        Stage.ADVERSARIAL_REVIEW,
        Stage.COMMIT,
        stamp=OK,
        pass_verdict_trees=[],
        current_tree="abc123",
    )
    with pytest.raises(LifecycleError, match="green stamp"):
        validate_transition(
            Stage.ADVERSARIAL_REVIEW,
            Stage.COMMIT,
            stamp=RED,
            pass_verdict_trees=[],
            current_tree="abc123",
        )


def test_findings_loop_back_under_cap() -> None:
    """Findings loop back under cap."""
    validate_transition(Stage.ADVERSARIAL_REVIEW, Stage.GATES, review_cycles=2)


def test_findings_loop_blocked_at_cap() -> None:
    """Findings loop blocked at cap."""
    with pytest.raises(LifecycleError, match="cap"):
        validate_transition(Stage.ADVERSARIAL_REVIEW, Stage.GATES, review_cycles=3)


def test_no_stage_jumping() -> None:
    """No stage jumping."""
    with pytest.raises(LifecycleError):
        validate_transition(Stage.READY, Stage.GATES, stamp=OK)
    with pytest.raises(LifecycleError):
        validate_transition(Stage.IMPLEMENTING, Stage.DONE)


def test_blocked_reachable_from_anywhere() -> None:
    """Blocked reachable from anywhere."""
    for stage in Stage:
        if stage is Stage.BLOCKED:
            continue
        validate_transition(stage, Stage.BLOCKED)


def test_blocked_returns_only_to_ready() -> None:
    """Blocked returns only to ready."""
    validate_transition(Stage.BLOCKED, Stage.READY)
    with pytest.raises(LifecycleError):
        validate_transition(Stage.BLOCKED, Stage.GATES, stamp=OK)
