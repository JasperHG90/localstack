---
type: plan
title: 'Plan: bifrost-ready-detach'
description: Make null_resource.bifrost_ready wait for the new Bifrost allocation, not the old one, by registering nomad_job.bifrost with detach = false.
tags:
- plan
slug: bifrost-ready-detach
epic: null
depends_on: []
priority: null
schema_version: '2.0'
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T12:51:47+00:00'
---

# bifrost-ready-detach

Relayed from: bifrost-update-2-6, reviewer finding f3: null_resource.bifrost_ready passed against the old 2.6.0 allocation, and the gateway then refused connections for about a minute while 2.7.0 started.

## Intent

`nomad_job.bifrost` in `deployments/applications/services.tf` keeps the
provider default `detach = true`, so `terraform apply` moves on once Nomad
accepts the job. `null_resource.bifrost_ready` then polls `/health` and can
reach the old allocation before it stops, so the gate's promise that virtual
keys are only touched against a live new gateway does not hold. Set
`detach = false`, as `nomad_job.openviking` already does, so the apply waits
for the deployment. `detach` is a provider setting, not part of the jobspec.
The provider still re-registers an identical spec, so Nomad records a new
job version and a deployment, but the running allocation is updated in place,
not restarted.

Outcome: a test pins `detach = false` on `nomad_job.bifrost`; a plan shows no
change to the running job; `just pre_commit` and `uv run --directory cli
pytest` pass.

## Problems

- P1: `null_resource.bifrost_ready` can pass against the old Bifrost allocation during an upgrade.

## Goals

- G1: Touch virtual keys only once the new gateway serves.

## Outcomes

### O1: nomad_job.bifrost waits for its deployment
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `deployments/applications/services.tf`, `cli/tests/test_bifrost_version.py`
- checked by: a test that `nomad_job.bifrost` sets `detach = false`
- seen by: operator

## Could invalidate this plan

- none
