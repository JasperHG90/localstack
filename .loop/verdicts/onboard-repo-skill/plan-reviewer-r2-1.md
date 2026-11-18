---
type: verdict
title: 'Verdict: onboard-repo-skill plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of onboard-repo-skill: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-18T14:47:33+00:00'
slug: onboard-repo-skill
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

p1 is resolved. Intent step 3 now saves a plan per root with `-out`, checks
it against a named list of expected changes, stops on anything else, and
applies that same file. The recipes are no longer used for apply, so the
`always_run` replan problem is gone. Nothing in the revision or elsewhere
could break the plan. Risk 1 stays settled by spike 3.

## Checked

- Both justfiles. The infrastructure recipes run
  `eval "$(uv run localstack env)"` then terraform with
  `-var-file=./vars/prod.tfvars`, the same as the revision. The applications
  recipes use `localstack env` and `dotenv-filename` for
  `.devcontainer/.env`. The devcontainer already loads that file with
  `--env-file` (`.devcontainer/devcontainer.json:42`), so calling terraform
  directly loses no variables.
- `null_resource.firewall` (`deployments/infrastructure/services.tf:483`):
  `always_run = timestamp()` gets fixed at plan time in a saved plan, so
  applying the saved file matches what was checked.
- The applications root's `aws` provider reads SeaweedFS's admin keys
  through an ephemeral Vault read and its endpoint through
  `data.consul_service.seaweedfs` on port 8333
  (`deployments/applications/providers.tf`). Waiting for the S3 port before
  the applications plan is the right guard after the infrastructure apply
  restarts `nomad_job.seaweedfs`. Ephemeral values are opened again at apply
  of a saved plan, so they do not go stale in the file.
- The applications root has no `always_run` or `timestamp()` trigger, so
  its expected change list (the consumer's prefix map at
  `deployments/applications/services.tf:658`) is complete enough to check.
- Spike 3 README, as in round 1: APM leaves an unlisted skill folder alone.

## Findings

- p1: resolved. The saved plan file is the mechanism round 1 asked for.

## Notes

Two things the build will meet and need not change the plan. First, the
infrastructure root's `nomad.manage` provider and the `localstack env`
tokens have short TTLs (30m for the brokered Nomad management token,
`machine_roles.tf:55`). If the operator pauses long at the "stop and ask"
step, the saved plan's apply can 403. That fails safe: re-plan and check
again. The skill could say so. Second, a saved plan holds sensitive values
in plain text, so the scratch file should be deleted after apply.
