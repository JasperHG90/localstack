---
type: verdict
title: 'Verdict: onboard-repo-skill reviewer round 2'
description: 'reviewer verdict for round 2 of onboard-repo-skill: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-18T14:58:55+00:00'
slug: onboard-repo-skill
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

All three findings are fixed and the edits break nothing. The caller template now relies on the openviking-sync action's own default folders, the push reason is true, and the test-order rule is stated. Pass.

## Checked

- Gates: `loopctl gate stamp` from the worktree gave stamp green `91e89a2049abaac0d9b7852d8bbb1abd24177bc9b74e9e267649763f7ce43176`. pre_commit, cli_tests and rows r1, r2 and r3 pass.
- f1: `.github/actions/openviking-sync/action.yml` defaults `folders` to `docs` and `.okf`. The skill's new "folders" input states the same default (line 17). The template drops `with: folders:`, filters on `docs/**` and `.okf/**` (line 155), and lines 179-181 say to set `folders` and match `paths` for other folders. r3 still passes, since the openviking-sync step now has no `with` keys at all.
- f2: lines 140-143 now say the pinned SHA must exist on GitHub and `main` there should match what was applied. Both are true.
- f3: lines 70-73 say to add the caller in key order. `test_default_callers` compares `list(rendered["callers"].values())` against a list, and Terraform map iteration is sorted by key, so key order is the right rule.
- Round-1 note: each step-4 block is now a single shell call that does `cd <checkout>/...`, `eval "$(uv run localstack env)"` and the terraform command, with `<checkout>` and `<scratchpad>` placeholders explained at lines 84-87. The `init` hint for a fresh worktree sits in the same call. No leftover `$SCRATCH`.
- `Vault refused role <key>` at line 192 matches the error text in `.github/actions/lab-auth/action.yml:98`.

## Findings

- f1: resolved at SKILL.md lines 17-18, 155 and 179-181.
- f2: resolved at SKILL.md lines 140-143.
- f3: resolved at SKILL.md lines 70-73.
