---
type: verdict
title: 'Verdict: onboard-repo-skill plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of onboard-repo-skill: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-18T14:46:07+00:00'
slug: onboard-repo-skill
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Spike 3 settles the one listed risk. APM 0.33.0 left an unlisted
`.claude/skills/onboard-repo/` byte-identical through `apm install`,
`apm install --frozen` and `apm prune`, each run on a fresh tree, and no
tracked skill file changed. The repo matches what the plan says about the
caller map, the prefix map, the two exact-list tests, ADR 0031 and the
`.gitignore` layout. One gap needs fixing before the plan goes ahead: how the
skill gets from the plan it checked to an apply. The recipes it would use
cannot do that (p1). This needs a revision, not a rethink.

## Checked

- Spikes 1 to 3: README outcomes, stdout, run.json and `files/spike3.sh`.
  Spikes 1 and 2 were rightly superseded because of the APM case-duplicate
  error. Spike 3 starts each install from a clean tree, checks sha256 on both
  skill copies, and counts tracked skill files changed. It exited 0. Its gap
  (APM overwrites a skill with the same name as one it installs) does not
  apply, since no package ships `onboard-repo`.
- `deployments/infrastructure/variables.tf:135`: `vault_ci_callers` has the
  shape the plan assumes (key = role name, optional `ov_sync`). An `ov_sync`
  entry adds a `vault_jwt_auth_backend_role.github_ci` and a
  `vault_identity_oidc_role.ci_ov_sync`, changes the shared
  `vault_policy.ci_ov_sync` (that makes the three Vault resources), and
  changes `local.seaweedfs_iam` in `services.tf`. `always_run` is at
  `services.tf:492`.
- `deployments/applications/services.tf:658`: the `prefixes` jsonencode map
  exists. `cli/tests/test_lab_auth_action.py`: `test_default_callers` and
  `test_ov_sync_prefix_map` hold the exact lists the plan names.
- ADR 0031 and `.github/actions/lab-auth/action.yml`: the action picks the
  Tailscale identity itself and the Tailscale inputs default to empty, so a
  caller workflow with no Tailscale inputs is right.
- `.gitignore`: `/.claude/*` with re-includes for listed rules only. Adding
  `!/.claude/skills/`, `/.claude/skills/*` and `!/.claude/skills/onboard-repo/`
  is the same pattern the rules use.
- Justfiles: the infrastructure root has `plan` and `apply`. The applications
  root has `apply` only. Neither passes `-out` or `-auto-approve`.

## Findings

- p1: the plan-then-apply step has no way to apply the plan it checked. The
  recipes plan again and prompt on stdin, and `always_run` means the second
  plan always differs. Name the mechanism (a saved plan file, or the operator
  applies) so the "stop on anything else" check means something.

## Notes

The rest is one mechanism, so no split is needed. The Environment API call,
the `vault read` check and the pinned workflow text are details the build
will settle.
