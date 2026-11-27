---
type: verdict
title: 'Verdict: hermes-file-toolset reviewer round 1'
description: 'reviewer verdict for round 1 of hermes-file-toolset: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T09:49:27+00:00'
slug: hermes-file-toolset
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. Both `platform_toolsets` lists in
`deployments/applications/services/hermes.hcl` now name `file`, every entry
is a toolset upstream defines, and the new test fails on the old config.
The seven SKILL.md edits fix the same wrong name and belong in this ticket.
Nothing blocks.

## Checked

- Gates, re-run from the worktree with `loopctl gate stamp`: "pass gate
  pre_commit", "pass gate cli_tests", "pass eval-row r1", "stamp green:
  b76b4b5db7642ffc200e9a2385176d98175f8f7c43c9c948a4023935e3176ddf".
- Diff: the changes are uncommitted in the worktree (`git diff HEAD`), and
  HEAD equals main. Nine files: hermes.hcl (two lines), the test file, and
  seven SKILL.md lines.
- Correctness: read the rendered `platform_toolsets` block (hermes.hcl
  around line 330). Both lists are terminal, web, browser, memory, skills,
  file, cronjob. The plan-reviewer's r1 verdict checked each of these
  against upstream `toolsets.py` at v0.22.2 and v0.23.4. The test's
  allowlist is a subset of upstream names, which can only make the test
  stricter.
- Row r1: the test's `fails_when` is "any entry not in the list, or `file`
  missing from either list". I ran the test's regex and assertions in a
  scratch script against changed copies of the file. Original passes.
  `files` in telegram only fails, `files` in both fails, and removing `file`
  from email fails. The test also asserts that exactly email and telegram
  are parsed, so a regex that silently matches nothing cannot pass. The
  check holds what the row asks.
- Row r2 (judgment): this is a deploy-time check (gateway log with no
  "references unknown toolset", and a Telegram file read). It cannot be
  judged before the apply. It is not judged here and needs its evidence
  recorded after the deploy.
- Scope of the SKILL.md edits: `services.tf:296-298` folds every SKILL.md
  into the hermes job, so the agent reads these lines at runtime. "via the
  `files` toolset" points the agent at a name that does not exist. That is
  the same defect as P1, and the fix reaches G1 ("the toolsets the config
  means them to have"). The job gets re-registered by the hcl change
  anyway, so the skill edits add no extra apply. In scope.
- Consistency: grepped the repo (excluding `.loop/` and `.git`) for
  "files toolset" and `- files`. Nothing is left except the guard test's
  own string. No docs/ or .okf/ page names the toolset.
- The comment above `KNOWN_TOOLSETS` gives a reason the code cannot state
  (the upstream source and the silent-skip behavior), so it meets
  minimal-comments.

## Findings

None.

## Notes

- The plan's `touches` leaves out the seven SKILL.md files. That is fine
  for this ticket. A future plan could name them so the touched paths match.
- `KNOWN_TOOLSETS` cites v0.22.2. When `hermes-update-0-23` lands, update
  the comment's version if the set is re-checked.
