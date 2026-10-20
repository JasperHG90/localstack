---
type: verdict
title: 'Verdict: ov-fresh-instance plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ov-fresh-instance: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T14:38:02+00:00'
slug: ov-fresh-instance
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round 1 findings are resolved and I found no new risk that could break
the plan. Spike 4 shows the policy rename keeps the key, plans clean, and
cuts the key off the old bucket while the backup key still reads it. The
cutover now stops the openviking job before taking the baseline. Verdict: pass.

## Checked

- Spike 4 (exit 0): the README outcome, plus stdout. The apply replaced
  `aws_iam_user_policy.seaweedfs["openviking"]` (`openviking-openviking` to
  `openviking-openviking-v2`), the key id and secret were unchanged, the third
  plan was clean, and all 15 checks passed before and after a restart. The
  key was denied put, get, list and delete on `openviking`, kept full access
  to `openviking-v2`, and the backup key read both.
- The spike's `files/main.tf` uses the same shapes as
  `deployments/applications/storage.tf`: users keyed by name, the policy
  named `${each.key}-${each.value.bucket}`, and the backup policy built from
  `local.seaweedfs_durable_buckets`. Its limits (one node, two buckets, no
  restore user) do not touch the question. `storage.tf` has not changed
  since the spike's head. User `openviking` appears in one bucket only, so
  the `merge` keyed by user name has no collision after the move.
- Cutover order: the job is stopped first, and the hourly reflection sweep
  runs inside that job (`OV_REFLECT_*` in `openviking.hcl`), so nothing writes
  the old schema or bucket while the baseline runs. Hermes and leo-consumer
  have nowhere to write while it is down. The backup key keeps read access to
  `openviking`, so the post-cutover checksums can be taken with the same key.
- Apply order: infrastructure first creates the v2 host volume the job needs
  before the applications apply registers it. The plan already notes that the
  nightly backup fails between the two applies.
- Spikes 1 and 3 still settle the two-schema and OIDC bootstrap risks, as in
  round 1.

## Findings

- p1: resolved by spike:ov-fresh-instance/4, now listed under Could
  invalidate this plan.
- p2: resolved. The Cutover order stops the `openviking` job before it
  records the baseline.

## Notes

The eval still has no rows. That is not a plan risk. The Outcome has many
separate checks (bucket listing, old-store match, identity probe, Hermes
search, backup prefixes), and each will need a row.
