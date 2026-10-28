---
type: verdict
title: 'Verdict: aim-to-apm reviewer round 2'
description: 'reviewer verdict for round 2 of aim-to-apm: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-28T10:42:05+00:00'
slug: aim-to-apm
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

All three round 1 findings are fixed, and the fixes broke nothing. The
README names both things APM cannot install. The .gitignore comment explains
the slop-scan-for-docs whitelist line. The recipe test now pins the copied
rule set to the 7. My stamp is green.

## Checked

- `loopctl gate stamp` from the worktree: "stamp green:
  f4836b6b0b24cf8b6ad5166e65f1cdcca2aae9188218ac006820325d9437880f", with
  gates pre_commit and cli_tests and rows r1 to r8 passing.
- README.md lines 96 to 104: the paragraph now says APM cannot install two
  things, then names slop-scan-for-docs (committed in `.claude/rules/`) and
  caveman (added by hand). That matches the .gitignore whitelist and
  apm.yml. r7's README tests still pass on it.
- .gitignore lines 22 to 25: the comment now covers slop-scan-for-docs, and
  the whitelist lines are unchanged.
- cli/tests/test_agent_tooling.py: `test_opencode_rules_come_from_both_install_recipes`
  extracts every `.claude/rules/NAME.md` from each recipe and asserts the set
  equals RULES (the 6 APM rules plus slop-scan-for-docs). Both justfile cp
  lines name exactly those 7. A glob would also fail the set check because
  `*` matches the name pattern, and the explicit glob assertion stays.

## Findings

- f1: resolved. The set equality closes the "rule outside the 7" gap. The
  byte comparison is still conditional, but its docstring now names r8 as the
  proof on a clean checkout, which is the reason I asked for.
- f2: resolved in .gitignore.
- f3: resolved in README.md.
