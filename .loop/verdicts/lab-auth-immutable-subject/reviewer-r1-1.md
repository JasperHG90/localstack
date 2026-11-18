---
type: verdict
title: 'Verdict: lab-auth-immutable-subject reviewer round 1'
description: 'reviewer verdict for round 1 of lab-auth-immutable-subject: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-18T13:30:14+00:00'
slug: lab-auth-immutable-subject
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says. The new `tailscale-identity` step reads
`sub` from an OIDC token with an untrusted audience, picks the immutable-subject
client for `repo:JasperHG90@8079803/` and the legacy one otherwise, and leaves
explicit inputs alone. The Vault role and the prefix map are applied live. One
non-blocking docs finding: the summary bullet sits under "Open gaps" but no
longer names a gap.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass,
  r1 to r4 pass, stamp green 8492c94ac04c925f19feee05e7e9863e4219c46e8386d1c33f0c401b9743368b.
- r1: the test runs the real step script with a stubbed curl returning a JWT,
  parametrized over both subject formats, and asserts exact client ID and
  audience outputs. Swapping either branch fails it. The test payloads hold no
  `-` or `_`, so the url-safe `tr` is not exercised there. I checked it by
  hand with a payload that has both, and it decodes. The spike also ran it
  against a real token.
- r2: explicit client and audience come back unchanged for both formats, and
  the test asserts curl was never called.
- r3: asserts the rendered role's four bound claims and `ov_sync`, not the
  source text.
- r4: parses the prefix map and asserts it equals exactly the two entries.
- r5 (judgment): the how-to drops the second-identity step and the Tailscale
  inputs, steps renumber 1 to 4 without gaps, and the skeleton test passes. The
  reference adds a picking-rule table. ADR 0031 amends 0027's consequence, and
  `git diff HEAD` shows ADR 0027 unchanged. `kmctl check` passes.
- r6 (judgment): I re-ran `vault read auth/jwt-github/role/loop-engineering-harness-openviking-sync`.
  bound_claims are repository JasperHG90/loop-engineering-harness, ref
  refs/heads/main, environment lab, and workflow_ref
  .../openviking-sync.yaml@refs/heads/main. Policies are default and
  ci-ov-sync-loop-engineering-harness-openviking-sync, ttl 300. The live
  ov-sync-consumer job spec contains the loop-engineering-harness prefix.
- Grepped the repo for stale "second identity" and old-default references. The
  component page and the reference agree with the action.

## Findings

- f1: `.okf/summary.md` lists the CI bullet under "Open gaps". The edit
  removed "not yet applied", which was the only gap it named, so it now
  describes a working feature as open. Move it out of the list or name what is
  still open, and restore "logs in to Vault". Non-blocking: a plain text fix.

## Notes

If the token has no `sub`, `jq -er '.sub'` exits under `set -e` without a
`::error::` line. That is acceptable, since GitHub always sets `sub`.
