---
type: verdict
title: 'Verdict: lab-auth-check-errexit plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of lab-auth-check-errexit: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T06:42:59+00:00'
slug: lab-auth-check-errexit
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan is sound. The cause is confirmed and turning off `-e` in the step
fixes it without changing what the step reports, because the script already
counts failures in `fail` and exits 1 on its own. No unlisted risk could
break the approach.

## Checked

- Read the plan, the eval rows and `.github/workflows/lab-auth-check.yaml`.
  The step sets only `set -u`, so GitHub's `-e -o pipefail` applies.
  `closed()` runs `timeout 6 bash -c ...` as a plain statement, so a 124
  ends the script before `case $?`.
- Reproduced locally: under `bash --noprofile --norc -e -o pipefail`, a
  function that runs `timeout 1 sleep 3; case $? in 124) ...` exits 124
  before the case. With `set +e` first it reaches the case and goes on.
- `-e` hits other spots in the same step the same way: `code=$(curl ...)`
  in `reach()` and the token check (curl exits non-zero when nothing
  answers), and the `tailscale status | jq` pipeline under pipefail. Today
  those would end the script instead of printing a FAIL row. Turning off
  `-e` for the whole step fixes all of them, so the plan's scope is right.
- `cli/tests/test_lab_auth_action.py` already loads the workflow with
  `yaml` (`CHECK_WORKFLOW`), and `jq` is on PATH here, so the planned
  stub-based test can pull out the step's `run` and run it. It has to set
  `VAULT_TOKEN` and `VAULT_ADDR` because of `set -u`, which is a build
  detail.

## Findings

None.

## Notes

The plan lists no risks. I agree: this is a small change to one step,
backed by a reproduction and a live run.
