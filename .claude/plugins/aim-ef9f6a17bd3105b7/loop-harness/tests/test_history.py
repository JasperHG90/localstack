"""Gate-failure history: red stamps accumulate as append-only evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop_harness.cli import main
from loop_harness.config import CONFIG_FILE
from loop_harness.ctl import advance, register
from loop_harness.history import HISTORY_DIR, read_gate_failures
from loop_harness.ledger import Stage
from loop_harness.stamp import tree_fingerprint


def _configure(repo: Path, gates: list[str]) -> None:
    """Author a loop config with the given gate commands."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gates": gates}), encoding="utf-8")


def _activate(repo: Path, slug: str) -> None:
    """Register a ticket and move it into an active (stampable) stage."""
    register(repo, slug)
    advance(repo, slug, Stage.IMPLEMENTING)


def test_red_runs_accumulate_and_green_appends_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N red stamps leave exactly N events; a following green stamp adds none."""
    slug = "reddish"
    _configure(repo, ["false"])
    _activate(repo, slug)
    monkeypatch.chdir(repo)

    runs = 3
    for _ in range(runs):
        assert main(["stamp"]) == 1  # RED verdict

    events = read_gate_failures(repo, slug)
    assert len(events) == runs
    expected_tree = tree_fingerprint(repo)  # stable: config unchanged across runs
    for event in events:
        assert event["slug"] == slug
        assert event["at"]  # a recorded timestamp
        assert event["failed_gates"] == [{"command": "false", "exit": 1}]
        assert event["tree"] == expected_tree  # the tree the gates ran on

    _configure(repo, ["true"])
    assert main(["stamp"]) == 0  # GREEN verdict
    assert len(read_gate_failures(repo, slug)) == runs  # unchanged


def test_only_failing_gates_are_recorded(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mixed run records only the gates that exited non-zero."""
    slug = "mixed"
    _configure(repo, ["true", "false"])
    _activate(repo, slug)
    monkeypatch.chdir(repo)

    assert main(["stamp"]) == 1
    events = read_gate_failures(repo, slug)
    assert len(events) == 1
    assert events[0]["failed_gates"] == [{"command": "false", "exit": 1}]


def test_red_append_failure_does_not_crash_stamping(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken history write degrades to a warning; stamping still returns RED."""
    slug = "reddish"
    _configure(repo, ["false"])
    _activate(repo, slug)
    # Sabotage the per-slug log location: a file where the history dir must go.
    (repo / HISTORY_DIR).parent.mkdir(parents=True, exist_ok=True)
    (repo / HISTORY_DIR).write_text("not a directory\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    assert main(["stamp"]) == 1  # RED verdict survives the failed append


def test_no_active_ticket_records_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A red stamp outside the loop (no active ticket) attributes to no slug."""
    _configure(repo, ["false"])
    monkeypatch.chdir(repo)
    assert main(["stamp"]) == 1
    assert not (repo / HISTORY_DIR).exists()
