"""Per-ticket reflection: what worked and what did not, in a form the loop
can aggregate.

When a ticket closes, the loop records a reflection at
``.loop/reflections/<slug>.md``: a minimal frontmatter schema (so
``loopctl distill`` can count patterns before any prose is read) plus a
free-form body. ``ctl.done()`` refuses to close a ticket whose reflection is
absent or schema-invalid; it never grades the prose. Existence and schema are
mechanically verifiable ("code must"); reflection quality is a skill
instruction ("prompts may").

Reflections are agent-written, like verdicts, so they need no state-guard
carve-out (the guard covers only ``ledger.json`` and ``stamp.json``). ``.loop/``
is excluded from the tree fingerprint, so a reflection written late in the
lifecycle never stales a green stamp.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from loop_harness.history import count_gate_failures
from loop_harness.ledger import BlockerCode, load_ledger

REFLECTIONS_DIR = Path(".loop") / "reflections"

# Controlled friction vocabulary: recurring patterns the loop already knows how
# to count. New patterns use the ``other:<slug>`` escape hatch and can be
# promoted to a tag later (DECISIONS.md R3).
FRICTION_VOCAB = frozenset(
    {
        "prek-first-pass-rewrite",
        "pytest-basename-collision",
        "compound-stamp-commit",
        "reviewer-boilerplate",
        "vacuous-tests",
    }
)
OTHER_PREFIX = "other:"

_REQUIRED_FIELDS = ("slug", "friction", "worked")
_VALID_BLOCKERS = frozenset(c.value for c in BlockerCode)


class ReflectionStatus(StrEnum):
    """Verify outcome for a per-ticket reflection artifact."""

    VALID = "valid"
    ABSENT = "absent"  # no reflection written yet
    INVALID = "invalid"  # unreadable or schema-invalid


@dataclass(frozen=True)
class Reflection:
    """The judgment-only frontmatter of a reflection artifact.

    The mechanical numbers (``cycles``, ``gates_red``) are no longer carried
    here: ``distill`` derives them from the ledger and the gate-failure history,
    so the schema asks the agent only for what it alone can supply.

    Attributes
    ----------
    slug : str
        The ticket this reflection belongs to.
    blockers : tuple[str, ...]
        Blocker codes hit (values from ``ledger.BlockerCode``); agent-supplied.
    friction : tuple[str, ...]
        Friction tags from ``FRICTION_VOCAB`` or the ``other:`` escape hatch.
    worked : tuple[str, ...]
        Short tags for what went smoothly.
    harness_change : str | None
        Optional one-line harness-improvement suggestion.
    """

    slug: str
    blockers: tuple[str, ...]
    friction: tuple[str, ...]
    worked: tuple[str, ...]
    harness_change: str | None = None


@dataclass(frozen=True)
class ReflectionVerdict:
    """Result of verifying a reflection against the schema."""

    status: ReflectionStatus
    detail: str = ""
    reflection: Reflection | None = None

    @property
    def ok(self) -> bool:
        """Whether the reflection exists and satisfies the schema."""
        return self.status is ReflectionStatus.VALID


@dataclass(frozen=True)
class DistillSummary:
    """Aggregated frontmatter across every reflection, ranked by frequency.

    Attributes
    ----------
    reflections : int
        Count of valid reflections aggregated.
    friction : tuple[tuple[str, int], ...]
        ``(tag, count)`` pairs, most frequent first.
    blockers : tuple[tuple[str, int], ...]
        ``(code, count)`` pairs, most frequent first.
    worked : tuple[tuple[str, int], ...]
        ``(tag, count)`` pairs, most frequent first.
    cycles : tuple[tuple[str, int], ...]
        ``(slug, review_cycles)`` pairs derived from the ledger, one per
        aggregated reflection, ordered by slug. Authoritative over any number
        the reflection body carries.
    gates_red : tuple[tuple[str, int], ...]
        ``(slug, red-stamp count)`` pairs derived from the gate-failure history,
        one per aggregated reflection, ordered by slug. Authoritative over any
        number the reflection body carries.
    harness_changes : tuple[str, ...]
        The one-line suggestions collected across reflections.
    skipped : tuple[str, ...]
        Slugs of reflection files skipped because they were schema-invalid.
    """

    reflections: int
    friction: tuple[tuple[str, int], ...]
    blockers: tuple[tuple[str, int], ...]
    worked: tuple[tuple[str, int], ...]
    cycles: tuple[tuple[str, int], ...]
    gates_red: tuple[tuple[str, int], ...]
    harness_changes: tuple[str, ...]
    skipped: tuple[str, ...]


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Read the leading ``---`` fenced ``key: value`` block into a dict.

    Parameters
    ----------
    text :
        The full reflection file contents.

    Returns
    -------
    dict[str, str]
        Raw string values keyed by field name.

    Raises
    ------
    ValueError
        If the opening or closing ``---`` fence is missing, or a line inside
        the fence is not ``key: value``.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter opening '---'")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"frontmatter line is not 'key: value': {line!r}")
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    raise ValueError("missing frontmatter closing '---'")


def _parse_list(raw: str) -> list[str]:
    """Parse a single-line ``[a, b, c]`` flow list into its items.

    Parameters
    ----------
    raw :
        The raw frontmatter value.

    Returns
    -------
    list[str]
        The trimmed, non-empty items; an empty list for ``[]`` or ``""``.

    Raises
    ------
    ValueError
        If ``raw`` is non-empty but not wrapped in ``[]``.
    """
    raw = raw.strip()
    if not raw:
        return []
    if not (raw.startswith("[") and raw.endswith("]")):
        raise ValueError(f"expected a '[a, b]' list, got {raw!r}")
    inner = raw[1:-1].strip()
    if not inner:
        return []
    return [item.strip() for item in inner.split(",") if item.strip()]


def _valid_friction(tag: str) -> bool:
    """Whether a friction tag is a known vocabulary term or a valid escape."""
    if tag in FRICTION_VOCAB:
        return True
    return tag.startswith(OTHER_PREFIX) and len(tag) > len(OTHER_PREFIX)


def parse_reflection(text: str, slug: str) -> Reflection:
    """Parse and schema-validate a reflection artifact's frontmatter.

    The schema checks required-field presence, types, and the controlled
    friction/blocker vocabularies. It never grades the prose.

    Parameters
    ----------
    text :
        The full reflection file contents.
    slug :
        The ticket slug the file is expected to be for.

    Returns
    -------
    Reflection
        The validated frontmatter.

    Raises
    ------
    ValueError
        On any schema violation: a missing field, a slug mismatch, or an
        out-of-vocabulary friction tag or blocker code.
    """
    fields = _parse_frontmatter(text)
    missing = [f for f in _REQUIRED_FIELDS if f not in fields]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")
    if fields["slug"] != slug:
        raise ValueError(f"slug mismatch: frontmatter says {fields['slug']!r}, expected {slug!r}")

    blockers = _parse_list(fields.get("blockers", ""))
    bad_blockers = [b for b in blockers if b not in _VALID_BLOCKERS]
    if bad_blockers:
        raise ValueError(f"unknown blocker code(s): {', '.join(bad_blockers)}")

    friction = _parse_list(fields["friction"])
    bad_friction = [t for t in friction if not _valid_friction(t)]
    if bad_friction:
        raise ValueError(
            f"friction tag(s) not in the controlled vocabulary "
            f"(use 'other:<slug>' for a new pattern): {', '.join(bad_friction)}"
        )

    harness_change = fields.get("harness_change", "").strip() or None
    return Reflection(
        slug=slug,
        blockers=tuple(blockers),
        friction=tuple(friction),
        worked=tuple(_parse_list(fields["worked"])),
        harness_change=harness_change,
    )


def verify_reflection(repo: Path, slug: str) -> ReflectionVerdict:
    """Judge the reflection artifact for ``slug`` against the schema.

    Parameters
    ----------
    repo :
        Repository root.
    slug :
        Ticket slug whose reflection to verify.

    Returns
    -------
    ReflectionVerdict
        ``ABSENT`` when no file exists, ``INVALID`` when it fails the schema,
        ``VALID`` (carrying the parsed ``Reflection``) otherwise.
    """
    path = repo / REFLECTIONS_DIR / f"{slug}.md"
    if not path.exists():
        return ReflectionVerdict(
            ReflectionStatus.ABSENT, f"no reflection: run `loopctl reflect {slug}`"
        )
    try:
        reflection = parse_reflection(path.read_text(encoding="utf-8"), slug)
    except (OSError, ValueError) as exc:
        return ReflectionVerdict(ReflectionStatus.INVALID, f"invalid reflection: {exc}")
    return ReflectionVerdict(ReflectionStatus.VALID, reflection=reflection)


def scaffold_reflection(repo: Path, slug: str) -> Path:
    """Write a schema-valid reflection template for ``slug`` and return its path.

    Every field starts empty for the author to fill; the mechanical numbers are
    no longer templated because ``distill`` derives them. Refuses to overwrite
    an existing reflection so a partly-authored artifact is never clobbered.

    Raises
    ------
    FileExistsError
        If a reflection already exists for ``slug``.
    """
    path = repo / REFLECTIONS_DIR / f"{slug}.md"
    if path.exists():
        raise FileExistsError(f"{path} already exists; edit it instead")
    vocab = ", ".join(sorted(FRICTION_VOCAB))
    template = (
        "---\n"
        f"slug: {slug}\n"
        "blockers: []\n"
        "friction: []\n"
        "worked: []\n"
        "harness_change:\n"
        "---\n"
        "\n"
        "## What worked\n"
        "\n"
        "<!-- what went smoothly; add short tags to 'worked' above -->\n"
        "\n"
        "## What worked less well\n"
        "\n"
        f"<!-- tag friction above from: {vocab}\n"
        "     or use other:<short-slug> for a new pattern -->\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template, encoding="utf-8")
    return path


def _ranked(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    """Sort a tag counter by descending count, then tag name, for stable output."""
    return tuple(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def distill(repo: Path) -> DistillSummary:
    """Aggregate every reflection's frontmatter, ranked by tag frequency.

    Reads ``.loop/reflections/*.md``, counting friction tags, blocker codes,
    and ``worked`` tags across all schema-valid reflections and collecting the
    ``harness_change`` one-liners. For each aggregated reflection it derives the
    mechanical numbers from evidence: ``cycles`` from the ledger's
    ``review_cycles`` and ``gates_red`` from the gate-failure history. The
    derived numbers are authoritative; any number the reflection body carries is
    ignored. Schema-invalid files are skipped (their slugs are reported), never
    silently dropped, so distillation cannot hide a broken artifact.

    Parameters
    ----------
    repo :
        Repository root.

    Returns
    -------
    DistillSummary
        The aggregated, frequency-ranked view for the ``ticket-planner`` agent.
    """
    directory = repo / REFLECTIONS_DIR
    ledger = load_ledger(repo)
    friction: Counter[str] = Counter()
    blockers: Counter[str] = Counter()
    worked: Counter[str] = Counter()
    cycles: list[tuple[str, int]] = []
    gates_red: list[tuple[str, int]] = []
    harness_changes: list[str] = []
    skipped: list[str] = []
    count = 0
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        slug = path.stem
        verdict = verify_reflection(repo, slug)
        if not verdict.ok or verdict.reflection is None:
            skipped.append(slug)
            continue
        reflection = verdict.reflection
        friction.update(reflection.friction)
        blockers.update(reflection.blockers)
        worked.update(reflection.worked)
        if reflection.harness_change:
            harness_changes.append(reflection.harness_change)
        entry = ledger.entries.get(slug)
        cycles.append((slug, entry.review_cycles if entry is not None else 0))
        gates_red.append((slug, count_gate_failures(repo, slug)))
        count += 1
    return DistillSummary(
        reflections=count,
        friction=_ranked(friction),
        blockers=_ranked(blockers),
        worked=_ranked(worked),
        cycles=tuple(sorted(cycles)),
        gates_red=tuple(sorted(gates_red)),
        harness_changes=tuple(harness_changes),
        skipped=tuple(skipped),
    )


def format_distill(summary: DistillSummary) -> str:
    """Render a distillation as a briefing the ``ticket-planner`` agent consumes.

    Parameters
    ----------
    summary :
        The aggregated view from ``distill``.

    Returns
    -------
    str
        A plain-text summary: recurring friction ranked, blockers, what worked,
        and the collected harness-change suggestions.
    """
    if summary.reflections == 0:
        return "no reflections to distill: none found under .loop/reflections/"

    def _section(title: str, ranked: tuple[tuple[str, int], ...]) -> list[str]:
        if not ranked:
            return [f"{title}: (none)"]
        return [f"{title}:"] + [f"  {count:>3}x  {tag}" for tag, count in ranked]

    lines = [f"distilled {summary.reflections} reflection(s):", ""]
    lines += _section("recurring friction", summary.friction)
    lines += ["", *_section("blockers hit", summary.blockers)]
    lines += ["", *_section("what worked", summary.worked)]
    if summary.cycles or summary.gates_red:
        red = dict(summary.gates_red)
        lines += ["", "per-ticket mechanical facts (derived):"]
        lines += [
            f"  {slug}: {n} review cycle(s), {red.get(slug, 0)} red gate run(s)"
            for slug, n in summary.cycles
        ]
    if summary.harness_changes:
        lines += ["", "suggested harness changes:"]
        lines += [f"  - {s}" for s in summary.harness_changes]
    if summary.skipped:
        lines += ["", f"skipped (schema-invalid): {', '.join(summary.skipped)}"]
    lines += [
        "",
        "Hand the recurring friction above to the `ticket-planner` agent to "
        "author harness-improvement tickets.",
    ]
    return "\n".join(lines)
