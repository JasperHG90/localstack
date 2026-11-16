---
type: verdict
title: 'Verdict: remove-hermes-interactive plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of remove-hermes-interactive: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T12:06:39+00:00'
slug: remove-hermes-interactive
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No risk could break this plan. The workflow file is a leaf: nothing tracked
outside `.loop/` names it, so deleting it cannot break a test, gate, doc or
other workflow. The eval rows check what the intent claims.

## Checked

- `git grep -n hermes-interactive -- ':!.loop'` matches only the workflow
  itself. Other `hermes` hits are the Nomad `hermes` job and its docs, which
  have nothing to do with this file.
- `.pre-commit-config.yaml` scopes its hooks to `cli`, `scripts` and
  `.github/actions`, and does not list workflow files.
  `cli/tests/test_ci_workflow.py` reads only `ci.yaml`. The lab-auth and
  openviking-sync tests build `workflow_ref` from the callers in
  `deployments/infrastructure/variables.tf`, and hermes-interactive is not
  one of them, so no Vault `jwt-github` role is tied to it.
- `OLLAMA_API_KEY`: `claude-ollama.yaml` uses it at lines 60 and 126, so the
  secret stays used, as the intent says (row r2).
- The "agent on issue text" lines in decision 0027 and in the `variables.tf`
  description point at `claude-ollama.yaml`, not at this file, so they stay
  true once it is gone.
- Rows: r1 checks that the file is no longer tracked and that no tracked file
  outside `.loop/` names it. r3 runs the gates. Together they match the
  stated outcome.

## Findings

None.

## Notes

`claude-ollama.yaml` also fires on `issue_comment`. That is outside this
ticket's scope and does not affect it. The operator may want to look at its
permissions separately.
