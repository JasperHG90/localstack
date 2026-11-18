---
type: verdict
title: 'Verdict: onboard-repo-skill reviewer round 1'
description: 'reviewer verdict for round 1 of onboard-repo-skill: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-18T14:54:32+00:00'
slug: onboard-repo-skill
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The skill is correct where it counts. An agent following it ends up with an applied onboarding: lab Environment, a `vault_ci_callers` entry, the prefix map, the exact-list tests, two applies from saved and checked plans, a `vault read` check, commit through the loop, a push only after asking, and a pinned caller workflow with no Tailscale inputs. The expected-plan list matches every resource keyed on `var.vault_ci_callers`. Three non-blocking fixes remain. The one that matters is f1: the caller template narrows the synced folders to `docs` without asking.

## Checked

- Gates: `loopctl gate stamp` from the worktree, stamp green `eabd7f93...2020`. pre_commit, cli_tests, and rows r1, r2 and r3 pass.
- r1: the test runs `git check-ignore -q` on the file and asserts exit code 1, then checks the front matter name and description. I confirmed by hand that `git check-ignore -v` ignores `.claude/skills/foo/SKILL.md` and not the onboard-repo one, and that the `.claude/rules` exceptions still hold.
- r2: the test collects backticked tokens that contain `/` and end in an extension or `/`, and asserts each exists. Placeholders with `<>`, `$SCRATCH` paths and ARNs fall outside the pattern, as they should. A misspelled real path would fail it.
- r3: the test parses the single yaml block that names `lab-auth@`. It asserts no pull_request or pull_request_target, `id-token: write`, `environment: lab`, `with` keys within each action's declared inputs, and no Tailscale inputs. That covers fails_when.
- r4 (judgment): passes. The skill forbids `just apply` and a bare `terraform apply`, and the reason it gives matches both justfiles (`terraform apply -var-file=...` re-plans and prompts). It saves with `-out` and applies only that file. It stops and shows the operator anything outside the expected list for both roots, and it never pipes `yes`.
- r5 (judgment): passes. Every step in the plan's intent is there. The how-to links the skill under Additional resources, and the four-section skeleton is unchanged.
- The expected plan, checked against code: `vault_jwt_auth_backend_role.github_ci` (machine_roles.tf, for_each on the variable); `vault_identity_oidc_role.ci_ov_sync` (oidc.tf) and `vault_policy.ci_ov_sync` (machine_roles.tf), both limited to ov_sync callers; `nomad_job.seaweedfs` through `local.seaweedfs_ci_callers` and `seaweedfs_iam` (policy and role `ci-<key>`, resource `arn:aws:s3:::ov-sync/<repo>/*`); `null_resource.firewall` with `always_run = timestamp()` in infrastructure only. The applications firewall and bifrost_ready have no always-changing triggers, so "only `nomad_job.ov_sync_consumer`" is right. No other resource reads the variable.
- `192.168.2.29:8333` is SeaweedFS's S3 and IAM port, which the applications aws provider reads through Consul. `uv run localstack env` works from `deployments/applications`. `vault read auth/jwt-github/role/<key>` matches the mount, and the bound_claims are the four named.
- ADR 0031 and lab-auth's `tailscale-identity` step: no Tailscale inputs are needed for either subject format. The `route-ask` skill exists in the loop-harness plugin.

## Findings

- f1: the `folders: docs` override and the `docs/**`-only paths filter, explained above. This is a design choice the skill makes for the operator without asking.
- f2: a false reason for pushing first.
- f3: the order of the exact list is not stated. It is self-correcting through the test run.

## Notes

Step 4's commands share `cd`, `eval` and `$SCRATCH` across code blocks. An agent whose shell resets between calls has to re-run `eval "$(uv run localstack env)"` and spell out its scratchpad path. The skill's 403 note covers the expired-token case, so I am not raising it as a finding.
