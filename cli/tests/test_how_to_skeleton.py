"""Every page in docs/how-to/ has the shape .claude/rules/how-to-skeleton.md sets.

A reader at work scans for the next command, so the four sections, their order
and the step numbering are the same on every page.
"""

import re
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
HOW_TO_DIR = REPO_ROOT / "docs" / "how-to"

SECTIONS = ["Introduction", "Prerequisites", "Directions", "Additional resources"]
HEADING = re.compile(r"^(#{1,6}) (.*\S)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
STEP = re.compile(r"^Step (\d+): \S")


def headings(text: str) -> list[tuple[int, str]]:
    """(level, text) of every markdown heading outside fenced code blocks."""
    found = []
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else HEADING.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2)))
    return found


def skeleton_errors(text: str) -> list[str]:
    """Every way a page departs from the how-to skeleton. Empty means conformant."""
    found = headings(text)
    errors = []

    titles = [t for level, t in found if level == 1]
    if len(titles) != 1 or not titles[0].startswith("How to "):
        errors.append(f"needs exactly one H1 starting 'How to ', found {titles}")
    elif found[0] != (1, titles[0]):
        errors.append("the H1 must be the first heading")

    h2 = [t for level, t in found if level == 2]
    if h2 != SECTIONS:
        errors.append(f"H2 sections must be exactly {SECTIONS}, found {h2}")

    steps: list[int] = []
    current_h2 = None
    for level, heading in found:
        if level == 2:
            current_h2 = heading
        elif level > 2:
            match = STEP.match(heading)
            if level != 3 or current_h2 != "Directions" or not match:
                errors.append(
                    f"heading below H2 must be '### Step N: ...' in Directions: {heading!r}"
                )
            else:
                steps.append(int(match.group(1)))
    if steps != list(range(1, len(steps) + 1)) or not steps:
        errors.append(f"steps must be numbered from 1 without gaps, found {steps}")

    return errors


def how_to_pages() -> list[Path]:
    return sorted(HOW_TO_DIR.glob("*.md"))


def test_how_to_pages_exist() -> None:
    """Self-check: an empty folder would let every other test here pass vacuously."""
    assert how_to_pages(), f"no how-to pages found under {HOW_TO_DIR}"


@pytest.mark.parametrize("page", how_to_pages(), ids=lambda p: p.name)
def test_how_to_page_follows_the_skeleton(page: Path) -> None:
    assert skeleton_errors(page.read_text()) == []


GOOD = """# How to do a thing

## Introduction
Text.
## Prerequisites
- A thing.
## Directions
### Step 1: Do it
```bash
# a shell comment, not a heading
```
### Step 2: Check it
## Additional resources
- A link.
"""


@pytest.mark.parametrize(
    ("page", "expected_fragment"),
    [
        (GOOD.replace("# How to do", "# Doing"), "H1"),
        (GOOD.replace("## Prerequisites\n", ""), "H2 sections"),
        (GOOD.replace("### Step 2", "### Step 3"), "without gaps"),
        (GOOD.replace("### Step 2: Check it", "### Checking"), "Step N"),
        (GOOD.replace("### Step 1: Do it", "#### Step 1: Do it"), "Step N"),
        (GOOD + "## Troubleshooting\n", "H2 sections"),
    ],
)
def test_skeleton_errors_catch_each_departure(page: str, expected_fragment: str) -> None:
    errors = skeleton_errors(page)
    assert any(expected_fragment in e for e in errors), errors


def test_skeleton_errors_accept_a_conformant_page() -> None:
    assert skeleton_errors(GOOD) == []
