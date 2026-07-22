"""Eval marker: the content-blind, slug-bound presence-plus-schema validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from loop_harness.evals import (
    EVALS_DIR,
    EvalStatus,
    eval_marker_present,
    verify_eval,
)

SLUG = "some-ticket"


def _write(repo: Path, slug: str, body: str) -> None:
    """Write an eval marker file for ``slug``."""
    path = repo / EVALS_DIR / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_absent_marker_is_not_present(repo: Path) -> None:
    """No file yields ABSENT and a false presence check."""
    verdict = verify_eval(repo, SLUG)
    assert verdict.status is EvalStatus.ABSENT
    assert not verdict.ok
    assert eval_marker_present(repo, SLUG) is False


def test_valid_marker_is_present(repo: Path) -> None:
    """A slug-bound header plus one scenario row is VALID."""
    _write(repo, SLUG, f"eval: {SLUG}\n\n- given X, expect Y\n")
    verdict = verify_eval(repo, SLUG)
    assert verdict.status is EvalStatus.VALID
    assert verdict.ok
    assert eval_marker_present(repo, SLUG) is True


def test_missing_header_is_invalid(repo: Path) -> None:
    """A scenario row without the header line fails the schema."""
    _write(repo, SLUG, "- given X, expect Y\n")
    assert verify_eval(repo, SLUG).status is EvalStatus.INVALID


def test_wrong_slug_header_is_invalid(repo: Path) -> None:
    """A header naming another slug does not clear this ticket's gate (slug-bound)."""
    _write(repo, SLUG, "eval: other-ticket\n\n- given X, expect Y\n")
    verdict = verify_eval(repo, SLUG)
    assert verdict.status is EvalStatus.INVALID
    assert SLUG in verdict.detail


def test_header_only_is_invalid(repo: Path) -> None:
    """The header alone, with no scenario row, is a stub and fails."""
    _write(repo, SLUG, f"eval: {SLUG}\n")
    assert verify_eval(repo, SLUG).status is EvalStatus.INVALID


def test_empty_file_is_invalid(repo: Path) -> None:
    """An empty marker fails the schema."""
    _write(repo, SLUG, "")
    assert verify_eval(repo, SLUG).status is EvalStatus.INVALID


@pytest.mark.parametrize("row", ["- dash item", "* star item", "| a | b |"])
def test_scenario_row_styles(repo: Path, row: str) -> None:
    """List (``-``/``*``) and table (``|``) rows all count as scenario rows."""
    _write(repo, SLUG, f"eval: {SLUG}\n\n{row}\n")
    assert verify_eval(repo, SLUG).status is EvalStatus.VALID


def test_content_is_not_graded(repo: Path) -> None:
    """The check is content-blind: a gibberish row still validates the shape."""
    _write(repo, SLUG, f"eval: {SLUG}\n\n- qwzx plover frob\n")
    assert eval_marker_present(repo, SLUG) is True
