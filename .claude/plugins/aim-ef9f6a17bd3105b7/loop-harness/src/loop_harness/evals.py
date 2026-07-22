"""Per-ticket eval marker: the Definition of Done authored before code.

When ``require_eval`` is set, a ticket cannot enter ``implementing`` until an
eval marker exists at ``.loop/evals/<slug>.md``: a scenario set an interactive
skill co-authors with the operator, so the DoD is concrete before work starts
("the eval is the spec"). The harness is CONTENT-BLIND — it checks presence and
a minimal, slug-bound schema, never the eval's substance — exactly as the
commit gate checks a verdict's ``verdict:``/``tree:`` lines without reading the
review.

Unlike a verdict, the marker is NOT tree-bound: the eval is authored before any
code exists, so there is no tree to bind to. The gate is presence plus shape
only, which makes it an activation-energy speed bump, not commit-gate-strength
enforcement — the real forcing function is the interactive skill. Binding the
header to the slug raises the cost of clearing the gate with a copied stub;
that is the intended strength and no more.

Eval files are skill-written, like verdicts and reflections, so they need no
state-guard carve-out (the guard covers only ``ledger.json`` and
``stamp.json``). ``.loop/`` is excluded from the tree fingerprint, so authoring
a marker never stales a green stamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

EVALS_DIR = Path(".loop") / "evals"


class EvalStatus(StrEnum):
    """Verify outcome for a per-ticket eval marker artifact."""

    VALID = "valid"
    ABSENT = "absent"  # no marker written yet
    INVALID = "invalid"  # unreadable or schema-invalid


@dataclass(frozen=True)
class EvalVerdict:
    """Result of verifying an eval marker against the minimal schema.

    Attributes
    ----------
    status : EvalStatus
        Whether the marker is valid, absent, or schema-invalid.
    detail : str
        Human-readable reason, for the transcript and error messages.
    """

    status: EvalStatus
    detail: str = ""

    @property
    def ok(self) -> bool:
        """Whether the marker exists and satisfies the minimal schema."""
        return self.status is EvalStatus.VALID


def _has_header(text: str, slug: str) -> bool:
    """Whether any line, stripped, is exactly ``eval: <slug>`` (slug-bound)."""
    want = f"eval: {slug}"
    return any(line.strip() == want for line in text.splitlines())


def _has_scenario_row(text: str) -> bool:
    """Whether any line is a scenario row: a ``-``/``*`` list item or a ``|`` table row."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")) or "|" in stripped:
            return True
    return False


def verify_eval(repo: Path, slug: str) -> EvalVerdict:
    """Judge the eval marker for ``slug`` against the minimal, content-blind schema.

    The schema is a slug-bound ``eval: <slug>`` header line (anywhere in the
    file) plus at least one scenario row (a ``-``/``*`` list item or a ``|``
    table row). The eval's substance is never graded: a single gibberish row
    satisfies the shape.

    Parameters
    ----------
    repo :
        Repository root.
    slug :
        Ticket slug whose eval marker to verify.

    Returns
    -------
    EvalVerdict
        ``ABSENT`` when no file exists, ``INVALID`` when it is unreadable or
        misses the header or a scenario row, ``VALID`` otherwise.
    """
    path = repo / EVALS_DIR / f"{slug}.md"
    if not path.exists():
        return EvalVerdict(EvalStatus.ABSENT, f"no eval marker: author {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return EvalVerdict(EvalStatus.INVALID, f"unreadable eval marker: {exc}")
    if not _has_header(text, slug):
        return EvalVerdict(EvalStatus.INVALID, f"eval marker missing 'eval: {slug}' header")
    if not _has_scenario_row(text):
        return EvalVerdict(EvalStatus.INVALID, "eval marker has no scenario rows")
    return EvalVerdict(EvalStatus.VALID)


def eval_marker_present(repo: Path, slug: str) -> bool:
    """Whether a schema-valid eval marker exists for ``slug`` (content-blind)."""
    return verify_eval(repo, slug).ok
