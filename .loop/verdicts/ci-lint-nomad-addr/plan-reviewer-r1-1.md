---
type: verdict
title: 'Verdict: ci-lint-nomad-addr plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ci-lint-nomad-addr: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T13:41:39+00:00'
slug: ci-lint-nomad-addr
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan holds. On a clean clone of the failing commit (44d969df), with a
fresh `.terraform` in both roots, an empty `.ssh/id_rsa` and an environment
stripped to `PATH`, `HOME` and `NOMAD_ADDR=http://127.0.0.1:4646`,
`scripts/tf_validate.sh` exits 0 for both roots. No other provider argument
depends on the devcontainer env. The "none" under Could invalidate this plan
is right.

## Checked

- Reproduced the CI failure: the same clean clone with no `NOMAD_ADDR`
  fails in `deployments/infrastructure` with exactly the run's error
  (`machine_roles.tf` line 63, provider "nomad", "address" is required).
- With `NOMAD_ADDR` only: infrastructure prints "Success! The configuration
  is valid, but there were some validation warnings" (the two
  `vault_kv_secret_v2` deprecation warnings at `secrets.tf` lines 179 and
  187, the same ones CI shows, which do not fail validate). Applications
  prints "Success! The configuration is valid." Script exit 0.
- The applications root was never reached in CI, because `set -e` stopped
  the script at infrastructure. Validated it on its own: it passes both with
  and without `NOMAD_ADDR`. Its `vault {}` (no `VAULT_ADDR`), `consul`
  (literal address), `aws`, `postgresql` and `bifrost` (values from
  ephemeral or resource references) need nothing from the env at validate.
  Infrastructure's `vault {}` and `google` (from `var.gcp_project`) also need
  nothing.
- Run 43863164828: every other prek hook passed and the knowledge job
  succeeded, so `terraform-validate` is the only red.
- `cli/tests/test_ci_workflow.py` exists and already parses the lint job's
  steps, so r1 extends a test that is already there.

## Findings

None.

## Notes

The local runs used linux_arm64 provider builds; CI uses amd64. CI already
got through `init` on this lock file, so that difference does not bear on the
plan.
