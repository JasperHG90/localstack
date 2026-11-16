---
type: verdict
title: 'Verdict: bifrost-router-priorities reviewer round 1'
description: 'reviewer verdict for round 1 of bifrost-router-priorities: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T15:12:57+00:00'
slug: bifrost-router-priorities
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. bifrost.hcl moves the four routing rules
to 10 to 13 with the passthrough first. The test now enforces unique
priorities, all above 3, with the passthrough first. The services.tf comment
sits outside any heredoc or jobspec. Apart from the ADR's original Decision
text, nothing in the repo still says the passthrough is at priority 0. The
gates are green. The remaining findings are about the knowledge bundle's own
rules (correction format, log line) plus line wrapping. None of them blocks.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, pass r2, stamp green f940c72a7a56f087207ee145c9d7b87b40a4bcc951b965ca33fab600d8d6caa7.
- `uv run --directory cli pytest tests/test_bifrost_router.py -q`: 9 passed.
  `kmctl check`: all checks passed.
- r1: test_complexity_router sorts by priority and asserts the set size equals
  the list length (catches a shared priority), checks `min > 3` (catches any
  rule at 3 or below), and requires the lowest one to carry the passthrough CEL
  and the weight-only target (catches the passthrough not being first). Each
  part of fails_when is asserted. Setting the old 0 to 3 back would fail on min.
- r3 (judgment): this cannot be checked until the operator applies. The
  reasoning holds. Bifrost stops at the first matching rule. The hand-made
  rules at 0 to 3 run first and never name complexity_tier, so Claude Code
  requests keep their aliases and pay no classifier call. Router-key requests
  that miss those rules then reach 10 to 13 as before. The implementer's local
  2.3.1 reproduction (old config fatal, new config boots with eight rules) fits
  the error the plan quotes. r3 stays open for the operator's apply and the
  smoke run.
- Grepped the repo outside .git and .loop for priority 0 claims. The only one
  left is ADR 0029's Decision text, covered by f1.

## Findings

- f1: Turn the Consequences bullet into a `## Correction, 2026-11-16` section
  at the end of ADR 0029, following ADR 0006, 0011 and 0019. Do not edit the
  Decision text. Amending this ADR, not writing a new one, is the right call:
  it fixes a fact (the priority numbers) and does not reverse the choice.
- f2: Append a 2026-11-16 line to `.okf/log.md` naming
  `components/bifrost` and
  `decisions/0029-bifrost-routes-by-complexity-for-one-virtual-key-and-adds-jev`,
  with the reason.
- f3: Rewrap the two long lines.
