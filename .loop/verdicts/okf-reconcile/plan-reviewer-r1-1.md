---
type: verdict
title: 'Verdict: okf-reconcile plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of okf-reconcile: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T17:56:59+00:00'
slug: okf-reconcile
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Fail. The plan can work, but three things must change before the build:
commit the staged ADR 0015 work it measures against (p1), stop pointing okf
sources at docs/ pages the dependent tickets will delete (p2), and loosen
r4's link regex to the bundle's root-relative style (p3). The listed risk is
settled by operator acceptance. None of the three findings invalidates the
plan.

## Checked

- Risk 1 (front matter `sources` edits on decision records): settled by the
  operator's acceptance, which the dispatcher relayed. r8 matches it: bodies
  must keep their old text as a prefix, front matter may change, and 0001 and
  0014 are left to r9.
- `kmctl check`: passes with 1 warning (summary behind). Confirmed.
- `kmctl review due --json`: 70 due (69 `unverified` and the summary), 444
  notices. By section: components 326, nodes 77, architecture 17,
  decisions 10, practices 7, proposals 7. By kind: git 349, loop 94, plus one
  `worktree:` source (`components/hermes`) the plan does not name. Its target
  is tracked, so step 1 covers it.
- No concept has a `verified` entry. Once sources resolve, review_due.py
  adds `source changed` only when `verified_at` is set, so r2's "only
  unverified" can be met. Proposals given a `stale_after` must set a future
  date.
- The summary goes current when it is committed in the same commit as the
  concept edits (summary.py diffs from the summary's last commit to HEAD).
- `kmctl decision supersede`: needs an index entry for 0014 (it has one).
  It sets `status: deprecated`, appends Correction and Supersedes lines and a
  log line with backticked ids. That satisfies r7 and r9 and leaves no body
  rewritten.
- Eval rows r1, r2, r3, r5, r7, r8, r9 and r10 each assert their fails_when.
- Commit 48f52e2 exists and is the kmctl add commit the plan reads tickets
  from.

## Findings

- p1 (premise): the plan's baseline is staged, not committed. A worktree
  from main HEAD has 14 decisions, the staged .okf edits will conflict, and
  the two gitignored rules step 4 relies on are missing.
- p2 (design, r2): docs/ sources become unresolved again when the docs
  tickets that depend on this one delete or rename pages, and those tickets
  may not edit .okf/.
- p3 (test-mismatch, r4): the regex refuses `](/components/x.md)`, the
  link style 254 of the bundle's 261 section links use.

## Notes

- r5 tests only the first line of each `- ` bullet for the status word, so
  a wrapped invariant needs its status on the first line. The build will show
  this.
- r7 needs ids without `.md`. Older log lines use the `.md` form.
- Scope: 63 concepts and 444 sources, plus a manifesto and a summary. r11
  asks one reviewer to judge every concept against the code, which is a lot
  for one review round. To split, the cut is mechanical repointing (r1 to r3,
  r7, r8, r10) versus the audit, manifesto and summary (r4 to r6, r9, r11).
