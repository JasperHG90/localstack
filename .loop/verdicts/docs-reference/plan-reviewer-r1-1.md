---
type: verdict
title: 'Verdict: docs-reference plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of docs-reference: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T17:56:17+00:00'
slug: docs-reference
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The three listed risks are settled by evidence that answers them, and the
plan works as written. One eval row (r4) has a fails_when wider than the
outcome, so it must be fixed and looked at again.

## Checked

- Risk 1 (kmctl sections): spike docs-reconcile/3 added front matter to one
  page of each kind, including docs/reference/bootstrap-secrets.md, and
  `kmctl check` passed with no section finding. I read kmctl v0.10.0
  `review_due.py`. Docs pages are due only on `stale_after` or a source
  change, never for being unverified. `source not resolved` and
  `front matter unreadable` are the only notices it emits for docs. URL
  sources are skipped. So r2's 'any notice' matches the outcome.
- Risk 2 (pages that belong in .okf): spike 1 found 0 of 81 pages. Its
  reference residue (vault-human-auth G2, cli-login F2/F8) is covered by r5.
- Risk 3 (drift that is a code bug): spike 2 is enough for paths and
  recipes. The plan states the gap in prose claims and routes any bug to a
  new ticket (step 7).

Eval rows, run against the current tree:
- r1: fails on all 19 pages today, as it should. It globs only the top level,
  which is right because docs/reference/architecture/ holds only PNGs.
- r2: the JSON keys (`notices`, `path` ending in `.md`) match kmctl v0.10.0.
  On a shallow clone kmctl skips history and emits no notices, so the row
  would pass without checking anything. Eval runs in a full worktree, so this
  is not a finding.
- r3: passes today. The only current warning is .okf/summary.md.
- r4: 26 hits today. Most are real shorthand (bare `*.tf`, `services/grafana.hcl`,
  dash backend files). `embark.json` in registry-ui.md is a false positive (p1).
  Check `ov.conf.json`, `nginx.conf` and `index.html` page by page, but each
  does name a tracked file here.
- r5 is a judgment row and fits the work.

## Findings

- p1: r4 flags registry-ui's `embark.json`, a file in another codebase, against an unrelated tracked Grafana dashboard. Narrow its fails_when to honor the outcome's carve-out.

## Notes

The ticket is small, with one contract defect and no need to split it.
docs/README.md is shared with docs-howto and docs-explanation, and each
ticket edits only its own section, so concurrent merges are a minor conflict
risk, not a plan risk.
