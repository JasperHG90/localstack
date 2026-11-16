---
type: verdict
title: 'Verdict: ci-tailscale-access-reviewer-f3 reviewer round 1'
description: 'reviewer verdict for round 1 of ci-tailscale-access-reviewer-f3: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:09:03+00:00'
slug: ci-tailscale-access-reviewer-f3
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The login step now fails at the OIDC read when GitHub's response has no
usable `value`, before it masks anything or calls Vault. The new test checks
every clause of row r1's `fails_when`, and the gates are green. Pass.

## Checked

- Read the diff of `.github/actions/lab-auth/action.yml` and the full login
  step. `jq -er '.value // empty'` exits nonzero when there is no output.
  Under `set -euo pipefail`, that failure, or a curl failure, reaches the
  `|| { ::error::...; exit 1; }` branch. This is the same pattern the step
  already uses for the Vault token.
- Ran the step's script directly with a stub curl, both the fixed version and
  the old `jq -r .value` version. With `{}` or `{"value":null}`, the fixed
  script exits 1 with the `::error::` line, and no mask or Vault call happens.
  The old script prints `::add-mask::null`, calls Vault and exits 0. With
  `{"value":"abc"}`, both versions mask `abc` and log in, so the happy path is
  unchanged.
- Row r1: `test_login_fails_on_missing_oidc_value` runs the real step text
  read from action.yml under `bash -e -o pipefail`. It stubs only curl, which
  is the network boundary. It asserts a nonzero exit, no Vault call (marker
  file), no `::add-mask::null`, and an `::error::` line naming the OIDC token.
  Each assertion fails against the old line.
- Row r2 and the gates: `loopctl gate stamp` returned pass for pre_commit,
  cli_tests, eval-row r1 and eval-row r2. Stamp green
  bc6b7f8426c55786141380ab6d2e3c058d098580d6dd2b22bbdb831f4f0f07c0.
- Consistency: grep found no doc or `.okf` page that quotes the old
  `jq -r .value` line.

## Findings

None.

## Notes

The `::error::` message also fires when curl itself fails, for example on an
HTTP error from the token endpoint. curl's own `-sS` stderr line still prints
above it, so the cause stays visible.
