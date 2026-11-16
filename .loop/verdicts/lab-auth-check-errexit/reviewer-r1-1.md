---
type: verdict
title: 'Verdict: lab-auth-check-errexit reviewer round 1'
description: 'reviewer verdict for round 1 of lab-auth-check-errexit: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T06:51:01+00:00'
slug: lab-auth-check-errexit
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The fix is right and small. The check step now starts `set +e -u`, so an
expected 124 from `timeout` reaches the `case` in `closed()` instead of ending
the script under GitHub's `bash -e -o pipefail`. Failures are still counted in
`fail` and the final line still exits 1 on any FAIL row. The new test runs the
real step text under the exact GitHub bash invocation and would catch a
regression.

## Checked

- `loopctl gate stamp` from the worktree: pass on gate pre_commit, gate
  cli_tests, eval-row r1 and eval-row r2. Stamp green
  c03493bd96bf312ef2eceb64a9e70c184e63eeb1ae15341f40cbab35d3fbc104.
- `uv run --directory cli pytest tests/test_lab_auth_action.py -q`: 6 passed.
- r1: the test reads the step's `run` from the workflow YAML (not a copy),
  runs it with `bash --noprofile --norc -e -o pipefail` and stub curl,
  timeout and tailscale, and asserts five "timed out" rows, OVERALL=PASS and
  exit 0. That matches the row's fails_when.
- Mutation check in a scratch dir: the same script with `set -u` restored
  stops after the four token/reach rows with rc=124, which is the live failure
  and what the test asserts against. With a stub `timeout` that exits 1, the
  fixed script prints five "refused" FAIL rows, OVERALL=FAIL and rc=1, so
  turning off `-e` did not hide real failures.
- Read the whole step: `row` FAIL, an empty firebat lookup (pipefail failure
  of tailscale or jq) and the final `[ "$fail" = 0 ] && ... || exit 1` all
  still behave correctly without `-e`. `-u` stays on.
- Consistency: the new comment is accurate. No doc or `.okf` page mentions
  `set -u`, errexit or the step's shell flags.
- r3 is a live judgment row for after landing; not judged here, as briefed.

## Findings

None.
