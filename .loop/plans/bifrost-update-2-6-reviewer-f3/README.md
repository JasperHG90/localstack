---
type: plan
title: 'Plan: bifrost-update-2-6-reviewer-f3'
description: Deferred hardening from bifrost-update-2-6, reviewer finding f3 in review round 2.
tags:
- plan
- hardening
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T12:49:24+00:00'
slug: bifrost-update-2-6-reviewer-f3
status: draft
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# bifrost-update-2-6-reviewer-f3

Relayed from: bifrost-update-2-6, reviewer finding f3 in review round 2

## Intent

null_resource.bifrost_ready can pass against the old allocation. nomad_job.bifrost keeps the provider default detach = true, so the apply goes on as soon as Nomad accepts the job, and the /health poll can reach the 2.6.0 gateway before it stops. The 2.7.0 apply showed this: the gate passed, then the gateway refused connections for about a minute. The comment on the gate says virtual keys are only touched after the gateway is back up, which is not true. This change did not cause it, and this round changed no key. nomad_job.openviking already uses detach = false for the same reason. at deployments/applications/services.tf:941.

## Problems

<!-- One line per problem this ticket fixes: - P1: text. Every problem is
fixed by at least one outcome. -->

- P1: The problem this ticket fixes, in one line.

## Goals

<!-- One line per goal the fixes serve: - G1: text. Every goal is served by
at least one outcome. -->

- G1: What fixing it serves, in one line.

## Outcomes

<!-- One block per outcome: a heading ### O1: what changes, then exactly these
one-line bullets. kind: behaviour (stands alone), support (serves another
outcome) or follow-up. goal: a G id. fixes: a P id. needs: none, or the O ids
it needs first, comma-separated. touches: the paths, CLI verbs or keys it
changes, each in backticks, comma-separated (new: marks a file it creates).
checked by: the test or check that shows it. seen by: operator, calling code
or nobody. loopctl plan lint writes these to .loop/plans/SLUG/facts.json. -->

### O1: What changes, in one line
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `loopctl verb`
- checked by: the test that shows it works
- seen by: operator

## Could invalidate this plan

- none
