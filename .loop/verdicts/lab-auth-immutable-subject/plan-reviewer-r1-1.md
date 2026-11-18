---
type: verdict
title: 'Verdict: lab-auth-immutable-subject plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of lab-auth-immutable-subject: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-18T13:12:15+00:00'
slug: lab-auth-immutable-subject
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. The one listed risk is settled by
spike:lab-auth-immutable-subject/1, and the repo claims item 2 depends on hold.

## Checked

- Spike evidence (README, stdout, files/action.yml): in run 44310680589 a
  composite bash step in an `environment: lab` job read `sub`
  (`repo:JasperHG90@8079803/lab-auth-probe@1459171707:environment:lab`),
  picked client `T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL`, and passed it to
  `tailscale/github-action@v4` through step outputs. `tailscale up`
  succeeded and the reach table passed. The job without the environment got
  a 403, so the new credential keeps the `environment: lab` gate. The
  old-format branch did not run, but it keeps today's default credential,
  which works now, and `lab-auth-check.yaml` covers it after merge.
- `vault_jwt_auth_backend_role.github_ci` (machine_roles.tf) binds
  `repository`, `ref`, `environment` and `workflow_ref`, never `sub`, so the
  immutable subject does not affect the Vault login. The new entry yields the
  four bound claims the outcome names.
- `ov_sync = true` feeds `vault_identity_oidc_role.ci_ov_sync` (oidc.tf),
  `vault_policy.ci_ov_sync`, and `local.seaweedfs_ci_callers` (infrastructure
  services.tf), all keyed on `caller.repository`, so the new caller gets its
  own prefix with no further code.
- The consumer's `prefixes` map is in `deployments/applications/services.tf`
  as the plan says. The concurrent ov-sync-consumer-lock-scope plan does not
  touch it.

## Findings

None.

## Notes

Apply order (infrastructure, then applications) and the seaweedfs job
re-render from the new IAM entry follow the existing ov-sync pattern and are
build-time details.
