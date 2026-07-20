"""Reflection: schema parse/validate, the verdict branches, and distill."""

from __future__ import annotations

from pathlib import Path

import pytest

from loop_harness.ctl import advance, register
from loop_harness.ledger import Stage
from loop_harness.reflection import (
    REFLECTIONS_DIR,
    ReflectionStatus,
    distill,
    format_distill,
    parse_reflection,
    scaffold_reflection,
    verify_reflection,
)
from loop_harness.stamp import GateResult, write_stamp

VALID = """---
slug: some-ticket
cycles: 2
gates_red: 1
blockers: [cap-exceeded]
friction: [prek-first-pass-rewrite, other:flaky-network]
worked: [tests-first]
harness_change: add a reflect scaffold command
---

## What worked
tests-first kept the diff small.
"""


def _write(repo: Path, slug: str, body: str) -> None:
    """Write a reflection file for ``slug``."""
    path = repo / REFLECTIONS_DIR / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_parse_valid_reflection() -> None:
    """A well-formed reflection parses into its typed frontmatter."""
    reflection = parse_reflection(VALID, "some-ticket")
    assert reflection.cycles == 2
    assert reflection.gates_red == 1
    assert reflection.blockers == ("cap-exceeded",)
    assert reflection.friction == ("prek-first-pass-rewrite", "other:flaky-network")
    assert reflection.worked == ("tests-first",)
    assert reflection.harness_change == "add a reflect scaffold command"


def test_empty_lists_and_absent_harness_change_are_valid() -> None:
    """Presence and type are enough; empty lists and no suggestion pass."""
    body = (
        "---\nslug: t\ncycles: 0\ngates_red: 0\n"
        "blockers: []\nfriction: []\nworked: []\nharness_change:\n---\n"
    )
    reflection = parse_reflection(body, "t")
    assert reflection.friction == ()
    assert reflection.harness_change is None


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("no frontmatter here\n", "opening '---'"),
        ("---\nslug: t\ncycles: 1\n---\n", "missing required field"),
        (
            "---\nslug: other\ncycles: 1\ngates_red: 0\n"
            "blockers: []\nfriction: []\nworked: []\n---\n",
            "slug mismatch",
        ),
        (
            "---\nslug: t\ncycles: two\ngates_red: 0\n"
            "blockers: []\nfriction: []\nworked: []\n---\n",
            "must be an integer",
        ),
        (
            "---\nslug: t\ncycles: 1\ngates_red: 0\n"
            "blockers: [nope]\nfriction: []\nworked: []\n---\n",
            "unknown blocker code",
        ),
        (
            "---\nslug: t\ncycles: 1\ngates_red: 0\n"
            "blockers: []\nfriction: [made-up]\nworked: []\n---\n",
            "controlled vocabulary",
        ),
        (
            "---\nslug: t\ncycles: 1\ngates_red: 0\n"
            "blockers: []\nfriction: [other:]\nworked: []\n---\n",
            "controlled vocabulary",
        ),
    ],
)
def test_parse_rejects_schema_violations(body: str, match: str) -> None:
    """Every schema violation raises with a pointed message."""
    with pytest.raises(ValueError, match=match):
        parse_reflection(body, "t")


def test_verify_absent(repo: Path) -> None:
    """No file yields the absent verdict."""
    verdict = verify_reflection(repo, "some-ticket")
    assert verdict.status is ReflectionStatus.ABSENT
    assert not verdict.ok


def test_verify_invalid(repo: Path) -> None:
    """A schema-invalid file yields the invalid verdict with detail."""
    _write(repo, "some-ticket", "---\nslug: some-ticket\ncycles: 1\n---\n")
    verdict = verify_reflection(repo, "some-ticket")
    assert verdict.status is ReflectionStatus.INVALID
    assert "missing required field" in verdict.detail


def test_verify_valid(repo: Path) -> None:
    """A well-formed file yields the valid verdict carrying the reflection."""
    _write(repo, "some-ticket", VALID)
    verdict = verify_reflection(repo, "some-ticket")
    assert verdict.ok
    assert verdict.reflection is not None
    assert verdict.reflection.slug == "some-ticket"


def test_scaffold_is_valid_and_prefills_cycles(repo: Path) -> None:
    """The scaffold is schema-valid and seeds cycles from the ledger."""
    register(repo, "some-ticket")
    advance(repo, "some-ticket", Stage.IMPLEMENTING)
    write_stamp(repo, [GateResult("pytest", 0)])
    advance(repo, "some-ticket", Stage.GATES)
    advance(repo, "some-ticket", Stage.SELF_REVIEW)
    advance(repo, "some-ticket", Stage.ADVERSARIAL_REVIEW)
    advance(repo, "some-ticket", Stage.GATES)  # one findings loop -> review_cycles == 1

    path = scaffold_reflection(repo, "some-ticket")
    verdict = verify_reflection(repo, "some-ticket")
    assert verdict.ok
    assert verdict.reflection is not None
    assert verdict.reflection.cycles == 1
    with pytest.raises(FileExistsError):
        scaffold_reflection(repo, "some-ticket")
    assert path.exists()


def test_distill_aggregates_and_ranks(repo: Path) -> None:
    """Distill counts tags across reflections, ranks them, and skips invalids."""
    _write(repo, "some-ticket", VALID)  # friction: prek-first-pass-rewrite, other:flaky-network
    _write(
        repo,
        "b",
        "---\nslug: b\ncycles: 0\ngates_red: 0\n"
        "blockers: [cap-exceeded]\nfriction: [prek-first-pass-rewrite]\n"
        "worked: [small-diff]\nharness_change: cache prek\n---\n",
    )
    _write(repo, "broken", "---\nslug: broken\ncycles: 1\n---\n")

    summary = distill(repo)
    assert summary.reflections == 2
    # prek-first-pass-rewrite appears twice and ranks first
    assert summary.friction[0] == ("prek-first-pass-rewrite", 2)
    assert ("other:flaky-network", 1) in summary.friction
    assert summary.blockers == (("cap-exceeded", 2),)
    assert set(summary.harness_changes) == {"add a reflect scaffold command", "cache prek"}
    assert summary.skipped == ("broken",)


def test_distill_empty(repo: Path) -> None:
    """Distill over no reflections reports nothing to distill."""
    summary = distill(repo)
    assert summary.reflections == 0
    assert "no reflections to distill" in format_distill(summary)


def test_format_distill_renders_ranked_sections(repo: Path) -> None:
    """The rendered briefing ranks friction and names the ticket-planner."""
    _write(repo, "some-ticket", VALID)
    text = format_distill(distill(repo))
    assert "recurring friction" in text
    assert "prek-first-pass-rewrite" in text
    assert "ticket-planner" in text
