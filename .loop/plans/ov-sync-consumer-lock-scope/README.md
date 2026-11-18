---
type: plan
title: 'Plan: ov-sync-consumer-lock-scope'
description: Measure what holds OpenViking's folder lock during a sync burst, then make bursts fast.
tags:
- plan
slug: ov-sync-consumer-lock-scope
status: draft
epic: null
depends_on:
- ov-sync-consumer-lock-conflict
priority: null
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:04:40+00:00'
---

# ov-sync-consumer-lock-scope

Relayed from: ov-sync-consumer-lock-conflict, plan-reviewer finding p1 in plan round 1

## Intent

A 189-file sync took over 20 minutes because writes kept hitting
`HTTP 409: lock acquire timed out`, some for minutes. Measure, against a
scratch OpenViking account, what holds the lock (a concurrent write with
`wait: true`, or the `semantic_dag` folder summary), which path it covers
(the file, its folder, or folders above) and how long it is held. Then pick
between serializing writes per folder, a longer in-process wait, or a lower
pool. Outcome: the same 189-file burst finishes in a measured, much shorter
time with few or no lock 409s.

## Could invalidate this plan

- needs operator-provided access to a scratch OpenViking account for the spike
