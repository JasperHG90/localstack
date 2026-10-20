---
type: verdict
title: 'Verdict: ov-carry-over reviewer round 2'
description: 'reviewer verdict for round 2 of ov-carry-over: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T17:04:47+00:00'
slug: ov-carry-over
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 is fixed. `compare()` now drops `SAVE_MAP` (`.map.md`) from the
top-level names it rejects, beside the trees and root sidecars, and the
docstring says so. The comparison test passes an empty `allowed` set and
seeds `.map.md`, so it proves the default and not an `--allow`. Nothing
around the fix broke. Gates are green on my own stamp.

## Checked

- `loopctl gate stamp` from the worktree: `stamp green:
  aea5e215033d07065869ca84622289c71323b5db93a03910d7ceb6f1661d78cb`.
  pre_commit, cli_tests and rows r1 to r7 pass.
- scripts/ov_carry_over.py:54 defines `SAVE_MAP = ".map.md"` with an ADR
  0023 pointer. Line 228 subtracts it from the top-level set before the
  blog-scraper and unexpected-entry checks, so those still fire (the r6
  parametrized cases for `projects` and `blog-scraper` pass).
- cli/tests/test_ov_carry_over.py:411-414: `carry.compare(olds, files,
  top, set())` with `new_keys | {".map.md"}` must return no problems. If
  the default were removed, `.map.md` would produce an "unexpected
  top-level entry" problem and the assert would fail.
- Docs: the how-to's `--allow` line and the reference table still read
  true. The table lists the trees as the main accepted names. It leaves
  out the sidecars and the map, but it says nothing false.

## Findings

f1: resolved at scripts/ov_carry_over.py:228, and the test at
cli/tests/test_ov_carry_over.py:411-414 proves it.
