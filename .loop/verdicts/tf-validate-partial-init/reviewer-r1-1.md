---
type: verdict
title: 'Verdict: tf-validate-partial-init reviewer round 1'
description: 'reviewer verdict for round 1 of tf-validate-partial-init: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T15:09:12+00:00'
slug: tf-validate-partial-init
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. The script removes `.terraform/` and exits 1
only when its own init fails, and only inside the branch where `.terraform/` was
absent before, so it cannot remove a directory that existed before the run. The
three tests run the real script against a stub `terraform` and assert each row's
`fails_when`. Gates are green. One non-blocking docs finding: the OKF page
describing this script is stale.

## Checked

- `loopctl gate stamp` from the worktree: pass on gate pre_commit, gate
  cli_tests, and eval rows r1 to r4. Stamp green
  df651e0e3226853502fc9701a57e70d5fb7387c927d371e7379da1fb436d9d82.
- `scripts/tf_validate.sh` read in full. The `rm -rf` sits inside
  `if [ ! -d "${d}/.terraform" ]`, so a pre-existing directory is never
  removed. Under `set -e`, the `if !` form is needed so the cleanup runs at
  all. stdout is discarded as before, and init's stderr still reaches the user.
- r1: the stub creates `.terraform/providers` and then fails. The test asserts
  a non-zero exit, that the first call was init, and that `.terraform/` is
  gone. The old script (set -e exits with the directory left behind) fails
  this test, and a mutant that removes the directory without exiting goes on
  to exit 0, which the test also catches.
- r2: both roots get a `.terraform/terraform.tfstate` and validate fails. The
  test asserts the exact call list (one validate, no init) and that the file
  content is intact, which catches both an init and a removal.
- r3: an exact call-list match on init `-backend=false` and then validate for
  both roots, with exit 0.
- Comment against minimal-comments: it records why (a partial `.terraform/`
  would be trusted by the existence check on every later run), which the code
  cannot say. Acceptable. The file header stays true.
- Known and accepted: an init killed by a signal still leaves the directory.

## Findings

- f1 (docs, non-blocking): `.okf/components/terraform-roots.md` lines 204-209
  list `deployments/applications/modules/bucket` as a validated root. That
  module was removed in 83c34845 and the script never lists it. The page also
  says nothing about the new cleanup on a failed fresh init. The page names the
  script as a source, so it describes code this ticket changes. Fix the root
  list and add one sentence about the cleanup, then run `kmctl check`.
