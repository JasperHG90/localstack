---
type: verdict
title: 'Verdict: ovsq-keyless-local-sync plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ovsq-keyless-local-sync: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-27T19:09:27+00:00'
slug: ovsq-keyless-local-sync
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

p1 is fixed. No new risk could break the plan, so the verdict is pass.

## Checked

The p1 fix, against the SeaweedFS 4.48 source (~/.cache/spike-src/seaweedfs):

- `weed/s3api/s3api_sts.go`: `minDurationSeconds = 900`. The
  AssumeRoleWithWebIdentity handler calls `parseDurationSeconds`, which takes
  `maxSec` from the configured `maxSessionLength` ("12h" = 43200 in
  seaweedfs.hcl:144) and refuses only values below `minSec` or above `maxSec`.
  900 passes.
- `weed/iam/sts/sts_service.go` `validateSessionDurationSeconds` uses the same
  inclusive bounds (`< 900 || > maxSec`). `CalculateSessionDuration` uses the
  requested 900 and caps only from above.
- `weed/iam/integration/iam_manager.go` `capDurationByRole`: when a duration
  is requested, it only lowers it to the role's `MaxSessionDuration`. That
  field is optional, and when set it must be at least 3600, so it can never
  lower 900. The plan's role sets none.
- The session expires at `time.Now() + 900s` on the server, so the live
  "Expiration about 15 minutes out" assertion tests what the plan claims.

The rest of the plan:

- The revision only changes the CLI request, O4's checked_by and the prose.
  The facts in facts.json still match the prose. O4 is the only behaviour,
  and its needs (O1, O2, O3) are the ones its live check waits on.
- The listed risk is still settled by spike:ovsq-keyless-local-sync/1. Its
  harness uses the same `tokenDuration`/`maxSessionLength` config as
  production.
- The prose now says a first sync longer than 15 minutes resumes after a
  fresh `eval` and rerun. That matches ovsq writing its manifest after each
  batch, which round 1 checked.

## Findings

- p1: resolved. DurationSeconds=900 is sent and tested, and SeaweedFS 4.48 accepts it as the inclusive minimum, with nothing above it to lower or refuse it.
