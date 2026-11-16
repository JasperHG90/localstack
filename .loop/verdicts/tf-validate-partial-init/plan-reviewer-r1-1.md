---
type: verdict
title: 'Verdict: tf-validate-partial-init plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of tf-validate-partial-init: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T14:56:58+00:00'
slug: tf-validate-partial-init
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. The narrowed scope still fixes the reported
bug: every place that hit it (a ticket worktree, the temporary stamp worktree,
CI) starts without `.terraform/`. `scripts/seed_worktree.sh` copies only `.ssh`
and the two `prod.tfvars`, never `.terraform/`. So the broken directory in the
relayed failure was made by the script's own init, which is exactly the case
the plan handles. The removal rule ("only when this run created it") cannot
reach a developer's backend-initialized root, because such a root always
already has `.terraform/` and so never enters the init branch.

## Checked

- Read the plan, the signed eval rows r1 to r4, and `scripts/tf_validate.sh`.
  Today the script runs init only under `[ ! -d "${d}/.terraform" ]`, so the
  fix is a failure branch on that one init call.
- Spike 1: `terraform providers schema -json` reads Consul on a root
  initialized with its backend. This supports dropping the schema probe.
- Spike 3: on a root with a backend record, `init -backend=false` reads Consul
  and does not repair the root, but leaves the record unchanged. On a CI-shaped
  root it succeeds offline. This supports dropping the "repair an existing
  directory" case. The plan no longer depends on Terraform's error wording, so
  the gap between "Missing required provider" and 1.16.5's "no package for"
  text no longer matters.
- `scripts/seed_worktree.sh`: does not copy or link `.terraform/`, so worktrees
  init fresh and are covered by the fix.
- `.pre-commit-config.yaml` (`terraform-validate`, `pass_filenames: false`) and
  `.github/workflows/ci.yaml` (fresh runner, Terraform 1.16.5): both run the
  script against fresh or existing roots in the ways the plan assumes.
- Deletion safety: a developer root has `.terraform/` (it holds the backend
  record), so the `-d` test is true, init is skipped, and the root is never
  removed. If `.terraform` is a dangling symlink or a plain file, `-d` is
  false, and `rm -rf` on that path removes only the link or file, never a
  target. A `TF_DATA_DIR` override sends init somewhere else, but the removal
  still targets the literal `${d}/.terraform` path, so it stays safe.
- Eval: r1 (the stub creates `.terraform/`, then init fails, so the script
  must exit non-zero and leave no directory) checks the fix. r2 checks the
  safety promise (no init and no removal on an existing directory, even when
  validate fails). r3 checks that the normal path is unchanged. r4 runs the
  gates. `cli/tests/test_seed_worktree.py` exists as the pattern the test
  follows. The rows match the intent.

## Findings

None.

## Notes

Not findings. The build can settle these.

- If init is killed by a signal (Ctrl-C, a hook timeout) instead of exiting
  non-zero, a plain `if ! terraform init ...; then rm -rf ...` branch never
  runs, and the partial directory survives. The reported failure ("unexpected
  EOF") is a normal non-zero exit, so the plan covers it. An EXIT/INT trap
  guarded by a "this run created it" flag would also cover a kill, if the
  implementer wants that.
- No row covers this case: the script's own init succeeds and then validate
  fails. The directory should be kept, so later runs don't init again for
  nothing. Removing it there would be wasteful but harmless.
- If the first root's init fails, the script exits without validating the
  second root. That matches `set -e` today.
