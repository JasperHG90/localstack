"""docs/README.md lists every page under docs/, and every link in it resolves.

An index is believed, so a page it leaves out is a page nobody finds.
"""

import re
from pathlib import Path

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
INDEX = DOCS / "README.md"
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def linked_paths() -> set[Path]:
    return {
        (DOCS / target).resolve()
        for target in LINK.findall(INDEX.read_text())
        if not re.match(r"[a-z]+:", target)
    }


def test_index_links_resolve() -> None:
    assert [p for p in linked_paths() if not p.exists()] == []


def test_index_lists_every_page() -> None:
    pages = {p.resolve() for p in DOCS.rglob("*.md") if p != INDEX}
    pages |= {p.resolve() for p in (DOCS / "reference" / "architecture").glob("*.png")}
    assert pages, "found no pages under docs/, so this test would pass vacuously"
    assert sorted(str(p.relative_to(DOCS)) for p in pages - linked_paths()) == []
