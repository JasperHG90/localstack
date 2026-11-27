---
type: verdict
title: 'Verdict: bifrost-ready-detach plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of bifrost-ready-detach: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-27T13:26:20+00:00'
slug: bifrost-ready-detach
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk would break this plan. I checked both claims it rests on against
the provider source pinned in the lock file (hashicorp/nomad 2.5.2) and
against Nomad's register endpoint.

## Checked

**Changing `detach` does not change the running job.** `detach` is a schema
attribute only (`resource_job.go`: Optional, Default true). `CustomizeDiff`
returns early when the old and new jobspec are equal, so `modify_index`,
`task_groups` and `allocation_ids` are not marked as changing. The plan shows
one in-place update on `nomad_job.bifrost`: `detach: true -> false`. The
provider's `Update` is `resourceJobRegister`, so the apply does call
`Jobs().RegisterOpts` with the same job. That is a mechanical difference from
the Intent's "does not re-register". But Nomad's `Job.Register` skips the
Raft write when `specChanged` is false: no new version, and
`reply.JobModifyIndex` stays the existing one. It only writes a fresh eval,
which schedules nothing. With `detach = false` the provider watches that eval.
It ends with no new deployment (or the last successful one), so the apply
returns fast. r2 asks about a jobspec change or a replacement, and neither
happens. The reviewer should expect the in-place `detach` line in the plan and
should not count it as a failure. `sha1(nomad_job.bifrost.jobspec)` does not
move either, so `null_resource.bifrost_ready` is not replaced by this change.

**With `detach = false` the apply waits for the deployment.**
`monitorDeployment` follows the eval chain, then polls the deployment until it
is `successful`, and errors on `failed` or `cancelled`. `bifrost.hcl` has no
`update` block, but it is `type = "service"`. `api.Job.Canonicalize` fills in
`DefaultUpdateStrategy()` for service jobs, so a version bump does produce a
deployment. Health comes from checks, and the job has an HTTP `/health` check.
The job has static port 8080 and a hostname constraint, so the old allocation
has to stop before the new one is placed. By the time the deployment is
healthy, only the new allocation answers on 192.168.2.50:8080, and the gate
polls the new gateway.

**Nothing else lets the gate run early.** `null_resource.bifrost_ready`
depends on `nomad_job.bifrost`, and its jobspec trigger replaces it on each
redeploy. Every `bifrost_virtual_key` depends on the gate, and so does the
bifrost provider's endpoint (`providers.tf:80`). Once the job resource waits
for the deployment, the order is fixed.

## Findings

None.

## Notes

Things to know at build time. They are not plan risks:
- The provider's default update timeout is 5m, and Nomad's default
  `healthy_deadline` is also 5m. A slow store migration on a future upgrade
  would make the apply fail on the timeout instead of passing early. That is
  the safer failure.
- The check interval is 30s, so the deployment takes a little longer to turn
  healthy. That is expected.

The 2.0 facts match the prose: one behaviour outcome. It fixes P1, needs
nothing, and touches `services.tf` and `test_bifrost_version.py`, the two
files the prose changes.
