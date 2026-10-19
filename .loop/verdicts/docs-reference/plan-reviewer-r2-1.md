---
type: verdict
title: 'Verdict: docs-reference plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of docs-reference: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T18:06:02+00:00'
slug: docs-reference
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

p1 is resolved. The two other changes (r2 checks the whole bundle, and the
plan repoints `.okf` sources when a page is renamed or deleted) do not break
the plan. No open risk is left.

## Checked

- r4 on the current tree reports 25 hits, all real shorthand (bare `*.tf`,
  `grafana.hcl`, dash backend files, bootstrap playbooks). `embark.json` is
  gone. The command checks exactly what its fails_when says. It also skips
  tokens that start with `/` or `~`, which matches the outcome's runtime-path
  carve-out.
- r2 is now bundle-wide. Today it fails with 444 notices, all `source not
  resolved` under `.okf/` (git:SHA:PATH and loop: sources). This ticket
  cannot clear those, but it depends on okf-reconcile, whose plan and its
  eval r2 require an empty `notices` list. So once that ticket merges, a
  notice found here can only come from this ticket or a sibling that has
  already merged, and the sibling evals require zero notices too. The row
  checks exactly its fails_when.
- The repoint step: 10+ `.okf` concepts have both `sources` front matter and
  a `docs/reference/` mention. A rename would change only their sources and
  log.md. okf-reconcile's r8 checks decision bodies only, so editing a
  decision's front matter here does not conflict with that rule.
- The three risks are still settled by spikes docs-reconcile/1, /2 and /3,
  as in round 1.

## Findings

- p1 (resolved): r4 now allow-lists `embark.json`; its fails_when and the outcome name the allow-list, and a run on the current tree no longer flags it.

## Notes

Some `.okf` bodies mention `docs/reference/*.md` in prose and in backticks
(for example `.okf/components/dash.md`). The plan edits only `sources`. If a
rename leaves a markdown link in a body broken, `kmctl check` (r3, which
checks the exit code) will catch it during the build. The plan is audit in
place, so renames should be rare. This is not a finding.
