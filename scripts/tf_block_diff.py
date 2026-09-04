#!/usr/bin/env python3
"""Prove a Terraform reorganization moved blocks without editing them.

Parses every `.tf` in two directories into top-level blocks keyed by their
header (`resource "vault_policy" "admin"`), then compares the two sets. A block
that moved between files keeps its key and its body, so a pure move reports
nothing. An edited attribute, a dropped `depends_on`, or an attribute swapped
between two blocks all report.

    scripts/tf_block_diff.py <before-dir> <after-dir>

Exit 0 when the two sides are identical, 1 otherwise.

Why not diff sorted lines: sorting destroys block membership, so moving a line
from one block to another passes. That check has a false negative exactly where
this one is needed.

Heredoc bodies are held verbatim, including their `#` comments. They are part
of the string Terraform stores (a `vault_policy` document, an `rules_hcl`
block), so a comment edit inside one is a real change and must report.
"""

from __future__ import annotations

import difflib
import pathlib
import re
import sys
from collections import Counter
from collections.abc import Callable

HEREDOC_OPEN = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)")
COMMENT = re.compile(r"^\s*(#|//)")
QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')
TRAILING_COMMENT = re.compile(r"(#|//).*$")


def scannable(line: str) -> str:
    """The line with quoted strings and trailing comments blanked out.

    Brace counting and heredoc detection run on this rather than the raw line.
    A `}` inside a string or a comment would otherwise close a block early, and
    everything after it in that block would never be compared: a silent false
    negative in the one direction that matters. Strings are blanked before
    comments so a `#` inside a string does not truncate the line.
    """
    return TRAILING_COMMENT.sub("", QUOTED.sub('""', line))


def blocks(directory: pathlib.Path) -> Counter[tuple[str, str]]:
    """Every top-level block in the root, as (header, body) counted pairs.

    Counted rather than a dict: two `provider "nomad"` blocks share a header
    and are told apart by their bodies.
    """
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(directory.glob("*.tf")):
        lines = path.read_text().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line or line[0].isspace() or COMMENT.match(line):
                i += 1
                continue
            header = " ".join(line.split()).rstrip("{").strip()
            depth, body, tag = 0, [], None
            while i < len(lines):
                cur = lines[i]
                if tag is not None:
                    # Heredoc content is raw: the closing tag is the only thing
                    # that ends it, and its braces belong to the string.
                    if cur.strip() == tag:
                        tag = None
                else:
                    scan = scannable(cur)
                    opened = HEREDOC_OPEN.search(scan)
                    if opened:
                        scan = scan[: opened.start()]
                        tag = opened.group(1)
                    depth += scan.count("{") - scan.count("}")
                body.append(cur)
                i += 1
                if tag is None and depth <= 0 and len(body) > 0:
                    break
            # body[0] is the header line itself, which is already the key.
            # Comments before a block never reach here: the outer loop skips
            # them, so a rewritten header comment is not a body diff.
            found[(header, "\n".join(body[1:]))] += 1
    return found


SELF_TEST_ROOT = """
resource "vault_identity_oidc_client" "public_one" {
  name        = "a"
  client_type = "public"
}

resource "vault_identity_oidc_client" "confidential_one" {
  name        = "b"
  client_type = "confidential"
}

resource "vault_policy" "with_heredoc" {
  policy = <<-EOT
    # a comment Vault stores
    path "x" { capabilities = ["read"] }
    a stray } that must not close the block
  EOT

  description = "reached only if the heredoc was skipped whole"
}

resource "vault_policy" "with_braces_in_strings" {
  note        = "a trailing brace } inside a string"
  description = "reached only if strings were blanked before counting"
}
"""

# Each case names an edit the tool must report, and the parser branch that has
# to be right for it to notice. Every mutation is one `replace` on the root
# above, so a case that stops mutating anything fails loudly rather than
# passing vacuously.
SELF_TEST_CASES: tuple[tuple[str, Callable[[str], str]], ...] = (
    (
        "block swap (what a sorted-line diff misses)",
        lambda t: (
            t.replace('"public"', "\x00")
            .replace('"confidential"', '"public"')
            .replace("\x00", '"confidential"')
        ),
    ),
    (
        "comment edited inside a heredoc Vault stores",
        lambda t: t.replace("a comment Vault stores", "edited"),
    ),
    (
        "attribute after a heredoc holding an unmatched brace",
        lambda t: t.replace("reached only if the heredoc was skipped whole", "edited"),
    ),
    (
        "attribute after a string holding an unmatched brace",
        lambda t: t.replace(
            "reached only if strings were blanked before counting", "edited"
        ),
    ),
)


def sorted_body(text: str) -> list[str]:
    """The unsound check this tool replaces: comments dropped, lines sorted."""
    return sorted(
        line for line in text.split("\n") if line.strip() and not COMMENT.match(line)
    )


def self_test() -> int:
    """Check the tool reports every edit in SELF_TEST_CASES.

    Each case is an edit a reorganization must not make silently. Deleting the
    heredoc branch or the string blanking in `scannable` makes one of them go
    unreported, so this fails if either is removed.
    """
    import tempfile

    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        before = pathlib.Path(tmp) / "before"
        after = pathlib.Path(tmp) / "after"
        for d in (before, after):
            d.mkdir()
        (before / "main.tf").write_text(SELF_TEST_ROOT)
        baseline = blocks(before)

        if sum((baseline - blocks(before)).values()):
            print("SELF-TEST FAILED: a root differs from itself")
            return 1

        for name, mutate in SELF_TEST_CASES:
            mutated = mutate(SELF_TEST_ROOT)
            if mutated == SELF_TEST_ROOT:
                failures.append(f"{name} (mutation changed nothing)")
                continue
            (after / "main.tf").write_text(mutated)
            if not sum((baseline - blocks(after)).values()):
                failures.append(f"{name} (not detected)")

        # The swap case must also be invisible to a sorted-line diff, or it
        # does not demonstrate the false negative this tool exists to close.
        swapped = SELF_TEST_CASES[0][1](SELF_TEST_ROOT)
        if sorted_body(swapped) != sorted_body(SELF_TEST_ROOT):
            failures.append(
                "block swap (not multiset-preserving, so it proves nothing)"
            )

    for f in failures:
        print(f"SELF-TEST FAILED: {f}")
    if failures:
        return 1
    print(f"self-test passed: {len(SELF_TEST_CASES)} cases, all reported")
    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        return self_test()
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    before, after = (pathlib.Path(a) for a in sys.argv[1:3])
    lost = blocks(before) - blocks(after)
    gained = blocks(after) - blocks(before)

    headers = sorted({h for h, _ in lost} | {h for h, _ in gained})
    for header in headers:
        old = sorted(b for h, b in lost.elements() if h == header)
        new = sorted(b for h, b in gained.elements() if h == header)
        if not old:
            print(f"ADDED    {header}")
        elif not new:
            print(f"REMOVED  {header}")
        else:
            print(f"CHANGED  {header}")
            for o, n in zip(old, new):
                for d in difflib.unified_diff(
                    o.split("\n"),
                    n.split("\n"),
                    lineterm="",
                    n=1,
                    fromfile=str(before),
                    tofile=str(after),
                ):
                    print("    " + d)
    total = sum(lost.values()) + sum(gained.values())
    print(f"{total} differing block(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
