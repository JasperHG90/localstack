---
type: verdict
title: 'Verdict: bifrost-ready-detach reviewer round 1'
description: 'reviewer verdict for round 1 of bifrost-ready-detach: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T13:32:48+00:00'
slug: bifrost-ready-detach
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The code change is right and small. `nomad_job.bifrost` now sets
`detach = false`, which matches `nomad_job.openviking`. The new test pins the
setting inside the bifrost block. Gates are green. The one finding is
wording: the plan and r2 claim the change does not re-register the job, and
the live evidence shows it did, harmlessly. Fix the wording, not the code.

## Checked

- Gates, re-run by me with `loopctl gate stamp` from the worktree:
  `pass gate pre_commit`, `pass gate cli_tests`, `pass eval-row r1`,
  `stamp green: bb408f2c2a7b424ffbaa9e2d7fea3e1e8df7730fb31acb7866ddf0d78888a1e5`.
- Correctness: `null_resource.bifrost_ready` depends on `nomad_job.bifrost`
  and is replaced when the jobspec hash changes. With `detach = false`, a
  jobspec change now blocks the apply until the Nomad deployment succeeds.
  Bifrost is a service job with a check and static port 8080 on host
  networking, count 1. So the old allocation has stopped and the new one is
  healthy before the gate polls `/health`. That closes P1. When only
  `detach` changes, the jobspec hash stays the same, so the gate is not
  replaced and does not re-poll, which is correct.
- r1: `test_bifrost_job_waits_for_its_deployment` takes only the
  `resource "nomad_job" "bifrost"` block, up to its closing brace at column
  0, and needs an uncommented `detach = false` line inside it. Removing the
  line, setting it to true, or commenting it out all fail the test. It
  asserts the row's fails_when.
- r2 (judgment): I read the evidence in the briefing and checked the cluster
  read-only. `nomad job history bifrost` shows version 19 submitted at
  14:27:39 and stable. `nomad job history -p -version 19` shows no diff
  against 18. The latest deployment 2c950259 succeeded. Allocation 3e1235b1
  runs at version 19, and the 2.6/2.7 allocation b6471d9b stopped
  earlier. The jobspec did not change and the job was not replaced, so r2's
  fails_when is not met and the row passes. Its behavior text and the
  plan's Intent overstate the result (f1).
- Consistency: the new code comment is true and matches the openviking
  comment. The comment only says why `detach = false` is set, and makes no
  claim about re-registration. No doc under `docs/` or `.okf/` mentions
  `detach`.
- No checklist lines were printed for this round.

## Findings

- f1 (docs, not blocking): plan Intent line 29-30 and the r2 behavior say
  the change "does not re-register" the job. It does: the provider's Update
  calls Register, and Nomad bumps the version even when the spec is
  identical. The fix is to say what happened: an identical spec was
  re-registered, a new deployment ran, and the allocation was updated in
  place with no restart. I left `eval_row` unset on purpose. r2's
  fails_when is correct and passed, and setting it would block the ticket
  for the operator over wording. The plan reviewer's r1 verdict repeats the
  same claim. It is a historical record, so leave it alone.

## Notes

The version bump has a small side effect worth knowing. Every future change
to a provider-only argument on any `nomad_job` (detach, purge_on_destroy, and
so on) will add a Nomad job version and run a deployment. It will not
restart allocations when the spec is the same.
