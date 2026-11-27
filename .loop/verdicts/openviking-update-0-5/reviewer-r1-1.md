---
type: verdict
title: 'Verdict: openviking-update-0-5 reviewer round 1'
description: 'reviewer verdict for round 1 of openviking-update-0-5: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T13:21:27+00:00'
slug: openviking-update-0-5
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The code change is right and small. The pins, the jobspec env, the guard
script, the viking_write description and the three new tests all do what the
plan says. The gates are green, and the live job is healthy on v0.5.6. One
r4 sub-claim is missing: no one ran a Hermes viking_search, and the row
counts unrecorded evidence as a failure. That blocks. A handful of stale
version mentions in comments and one proposal page are non-blocking.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, r2, r3. Stamp green, fingerprint 3002309b2f52...06cb.
- Diff against main (uncommitted in the worktree, under
  loop/openviking-update-0-5). I read every changed file and both new tests.
- r1: test_openviking_version.py asserts the exact base and image strings
  in services.tf (as a one-element list, so a duplicate line fails too) and
  the sorted set of the two Dockerfile git tags. A branch or another tag
  fails it. Asserts the row.
- r2: test_check_openviking_config.py runs the real jobspec_failures on the
  committed openviking.hcl (must be empty) and on a copy with each removed
  key injected (must name it). It also checks that a commented line passes.
  The new `_removed_setting_failures` skips `#` lines and anchors on
  `NAME\s*=`, so MAX_DOCUMENTS is not caught by mistake. Asserts the row.
- r3: the new test asserts "must not exist" is gone and "overwrite" is in
  WRITE_SCHEMA's description. Asserts the row.
- r4 (judgment): I checked it myself. GET /health returned
  {"status":"ok","healthy":true,"version":"v0.5.6","auth_mode":"oidc"} and
  /ready returned 200. `nomad job status openviking` shows the latest
  deployment as successful and one running alloc at version 6. I accept the
  recorded find/search results (scores and timing look like a real reranked
  spread). I could not run a Hermes viking_search: alloc exec into hermes is
  refused to me. See f1.
- Consistency: the okf component page now matches the pins, and the
  check_openviking_config docstring now says ov_ext. A repo-wide grep for
  the removed keys, the old tags and "must not exist" turned up the stale
  mentions in f2.
- No checklist lines were printed for this round.

## Findings

- f1 (missing, blocking): r4's Hermes viking_search is not observed. Hermes
  goes through upstream's plugin, not the raw find call, so a 200 from
  /api/v1/search/find with a Vault token does not show that the plugin's
  request shape still works on 0.5.x. Run one viking_search through the
  deployed Hermes and record the result. The plugin delay explains why the
  viking_write description cannot be live yet. It does not explain the
  missing search, which needs no new hermes image.
- f2 (docs, non-blocking): fix the stale version mentions in services.tf:468,
  .okf/proposals/openviking-dashboard.md:47-49 and the justfile echo. These
  are free edits outside any heredoc or jobspec. The two openviking.hcl
  comments are inside the jobspec, so editing them re-registers the job. Fold
  them into the next jobspec change (the /health line can quote the v0.5.6
  response already recorded) or leave them, and say which you chose.

## Notes

The Dockerfile comment still says "ov-retrieval's diversity pass". That
wording is older than this change, and the package is now ov-ext. It is
harmless.
