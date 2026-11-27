---
type: verdict
title: 'Verdict: openviking-update-0-5 reviewer round 2'
description: 'reviewer verdict for round 2 of openviking-update-0-5: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T15:07:06+00:00'
slug: openviking-update-0-5
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round 1 findings are resolved. The free comment fixes are correct and
change nothing Terraform stores. The missing r4 evidence is now on record.
The gates are green on the new tree, and the change can be committed.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, r2, r3. Stamp green, fingerprint
  4ef60b48b175dcc071b2540395eba4e9ddc396d3064e85a5576eed8a801dd11a.
- `git diff HEAD` on the three files f2 named. The services.tf change is in
  the `###` block above `resource "nomad_job" "openviking"`, outside any
  heredoc or templatefile, so it is free. That matches the plan the
  implementer reports, with no change to nomad_job.openviking. The proposal
  page now names ov-postgres-v0.7.0, ov-ext-v0.8.0 and base 0.5.6, which
  match the Dockerfile and services.tf. The justfile echo and comment now
  say ov_ext.
- r4: the coordinator relays that on 2026-11-27, after v0.5.6-1 went live,
  the operator ran a memory search through the deployed Hermes over
  Telegram, against OpenViking 0.5.6, and it returned memories. Together
  with my own round 1 checks (/health v0.5.6, /ready 200, deployment
  successful) and the recorded find and search results, that covers every
  sub-claim of the row. I could not see this search myself. The evidence
  is the operator's report, passed on by the coordinator.
- No checklist lines were printed for this round.

## Findings

- f1: resolved. The Hermes viking_search evidence is now recorded, as
  above.
- f2: resolved. services.tf:468, .okf/proposals/openviking-dashboard.md:47-49
  and the justfile verify recipe are fixed. The two comments inside the
  openviking.hcl jobspec are left on purpose to avoid re-registering the
  job, which is the choice terraform-file-layout.md allows and which f2 asked
  the implementer to state.
