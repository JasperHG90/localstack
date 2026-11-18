---
type: plan
title: 'Plan: ov-sync-consumer-reviewer-f3'
description: Deferred hardening from ov-sync-consumer, reviewer finding f3 in review round 1.
tags:
- plan
- hardening
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T21:34:03+00:00'
slug: ov-sync-consumer-reviewer-f3
status: draft
epic: ci-lab-access
depends_on: []
priority: null
---

# ov-sync-consumer-reviewer-f3

Relayed from: ov-sync-consumer, reviewer finding f3 in review round 1

## Intent

Two events for the same key can be handled by two workers at once. Apply reads S3 before it takes the lock. If worker A reads v1, worker B then reads v2 and writes it, and A writes v1 after, OpenViking keeps v1. Catch-up compares only which files exist, so the stale content stays until the next event on that file. The delete-versus-recreate interleaving loses the file in the same way, but catch-up repairs that one. Serializing per key would close it. Any such fix must not acquire anything while it holds tree.Lock that a worker blocked on RLock already holds. at applications/ov-sync-consumer/internal/consumer/consumer.go:179.

## Could invalidate this plan

- none
