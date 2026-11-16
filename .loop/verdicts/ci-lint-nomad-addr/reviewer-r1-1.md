---
type: verdict
title: 'Verdict: ci-lint-nomad-addr reviewer round 1'
description: 'reviewer verdict for round 1 of ci-lint-nomad-addr: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T13:48:04+00:00'
slug: ci-lint-nomad-addr
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says and nothing more. The lint job's "Pre-commit hooks" step now sets a placeholder `NOMAD_ADDR`, and a new workflow test fails when that env entry is missing. Gates are green on this tree.

## Checked

- Diff (`git diff`, uncommitted): `.github/workflows/ci.yaml` adds `env: NOMAD_ADDR: http://127.0.0.1:4646` to the prek step only. The Install Nomad step and the knowledge job are untouched. `cli/tests/test_ci_workflow.py` adds `test_prek_step_sets_nomad_addr`.
- Premise: `provider "nomad" {}` in both roots' `providers.tf` and the aliased `provider "nomad"` at `deployments/infrastructure/machine_roles.tf:63` set no `address`, so the address comes from `NOMAD_ADDR`. Scoping the env to the prek step covers `terraform-validate`, which is the only hook that needs it.
- r1: the test finds the step whose `run` mentions `prek` and asserts that `env.NOMAD_ADDR` is truthy. With the env block removed, `.get("env", {}).get("NOMAD_ADDR")` returns None and the test fails, so it checks the row's fails_when. `uv run --directory cli pytest tests/test_ci_workflow.py -q` gives 2 passed.
- r2: covered by the stamp below.
- `loopctl gate stamp` from the worktree: pass on gate pre_commit, gate cli_tests, eval-row r1 and eval-row r2. Result: stamp green 25e400879e3a85401c62feae9e0af21eb5d4bb01e873756c6e9e95fa09a49f2e.
- r3 (judgment): this needs a CI run on main after the push, which I cannot see before commit. The plan reviewer reproduced CI's exact error with an empty env on a clean clone, and showed validate passing in both roots once `NOMAD_ADDR` was set. That makes the change the right one. r3 is still open until the post-push run is green.
- Consistency: the new YAML comment is accurate. The test file's module docstring still describes hook tools and the SSH key, and it says nothing that is now false. No docs claim that CI lacks `NOMAD_ADDR`.

## Findings

None.

## Notes

After the push, someone must check that the ci run on main is green for both lint and knowledge before r3 counts as met.
