"""Reflection: schema parse/validate, the verdict branches, and distill."""

from __future__ import annotations

from pathlib import Path

import pytest

from loop_harness.ctl import register
from loop_harness.history import append_gate_failure
from loop_harness.ledger import load_ledger, save_ledger
from loop_harness.reflection import (
    REFLECTIONS_DIR,
    ReflectionStatus,
    distill,
    format_distill,
    parse_reflection,
    scaffold_reflection,
    verify_reflection,
)
from loop_harness.stamp import GateResult

VALID = """---
slug: some-ticket
blockers: [cap-exceeded]
friction: [prek-first-pass-rewrite, other:flaky-network]
worked: [tests-first]
harness_change: add a reflect scaffold command
---

## What worked
tests-first kept the diff small.
"""

# The pre-shrink format still carries the mechanical numbers; the parser must
# tolerate them as now-unknown keys (R-D: old reflections still parse).
OLD_SCHEMA = """---
slug: some-ticket
cycles: 2
gates_red: 1
blockers: [cap-exceeded]
friction: [prek-first-pass-rewrite]
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
    assert reflection.blockers == ("cap-exceeded",)
    assert reflection.friction == ("prek-first-pass-rewrite", "other:flaky-network")
    assert reflection.worked == ("tests-first",)
    assert reflection.harness_change == "add a reflect scaffold command"


def test_shrunk_schema_validates_with_judgment_only() -> None:
    """A reflection with only judgment fields (no cycles/gates_red) is valid."""
    body = "---\nslug: t\nfriction: [prek-first-pass-rewrite]\nworked: [small-diff]\n---\n"
    reflection = parse_reflection(body, "t")
    assert reflection.friction == ("prek-first-pass-rewrite",)
    assert reflection.worked == ("small-diff",)
    assert reflection.blockers == ()  # optional, defaults empty
    assert reflection.harness_change is None


def test_old_schema_reflection_still_parses() -> None:
    """The pre-shrink format still parses; its stale numbers are ignored (R-D)."""
    reflection = parse_reflection(OLD_SCHEMA, "some-ticket")
    assert reflection.friction == ("prek-first-pass-rewrite",)
    assert not hasattr(reflection, "cycles")
    assert not hasattr(reflection, "gates_red")


def test_empty_lists_and_absent_harness_change_are_valid() -> None:
    """Presence and type are enough; empty lists and no suggestion pass."""
    body = "---\nslug: t\nblockers: []\nfriction: []\nworked: []\nharness_change:\n---\n"
    reflection = parse_reflection(body, "t")
    assert reflection.friction == ()
    assert reflection.harness_change is None


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("no frontmatter here\n", "opening '---'"),
        ("---\nslug: t\n---\n", "missing required field"),
        (
            "---\nslug: other\nfriction: []\nworked: []\n---\n",
            "slug mismatch",
        ),
        (
            "---\nslug: t\nblockers: [nope]\nfriction: []\nworked: []\n---\n",
            "unknown blocker code",
        ),
        (
            "---\nslug: t\nblockers: []\nfriction: [made-up]\nworked: []\n---\n",
            "controlled vocabulary",
        ),
        (
            "---\nslug: t\nblockers: []\nfriction: [other:]\nworked: []\n---\n",
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


def test_scaffold_is_valid_and_emits_no_numeric_fields(repo: Path) -> None:
    """The scaffold is schema-valid and templates no derived numeric fields."""
    register(repo, "some-ticket")
    path = scaffold_reflection(repo, "some-ticket")
    text = path.read_text(encoding="utf-8")
    assert "cycles:" not in text
    assert "gates_red:" not in text
    verdict = verify_reflection(repo, "some-ticket")
    assert verdict.ok
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


def test_distill_derives_numbers_ignoring_body(repo: Path) -> None:
    """Derived cycles/gates_red come from evidence, not the reflection body.

    The ledger records C review cycles and the history log holds N failure
    events; the body states contradictory numbers (old schema). Distill reports
    the derived C and N, not the self-reported ones.
    """
    slug = "derived"
    register(repo, slug)
    ledger = load_ledger(repo)
    ledger.entries[slug].review_cycles = 3  # C
    save_ledger(repo, ledger)
    for _ in range(2):  # N red gate runs
        append_gate_failure(repo, slug, [GateResult("uv run pytest", 1)], "deadbeef")
    # The body carries contradictory (stale) numbers that must be ignored.
    _write(
        repo,
        slug,
        f"---\nslug: {slug}\ncycles: 99\ngates_red: 99\n"
        "blockers: []\nfriction: []\nworked: []\n---\n",
    )

    summary = distill(repo)
    assert (slug, 3) in summary.cycles
    assert (slug, 2) in summary.gates_red
    text = format_distill(summary)
    assert f"{slug}: 3 review cycle(s), 2 red gate run(s)" in text


def test_distill_derives_zero_when_no_evidence(repo: Path) -> None:
    """A slug with no ledger entry and no history derives zero for both."""
    _write(repo, "some-ticket", VALID)
    summary = distill(repo)
    assert ("some-ticket", 0) in summary.cycles
    assert ("some-ticket", 0) in summary.gates_red


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
