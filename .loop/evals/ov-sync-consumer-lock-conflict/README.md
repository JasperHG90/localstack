---
type: eval
title: 'Eval: ov-sync-consumer-lock-conflict'
description: 'Definition of done for ov-sync-consumer-lock-conflict: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T08:43:19+00:00'
slug: ov-sync-consumer-lock-conflict
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 9a3f5e213c85eeeead8be53c3eb9cb08d474f48973accf93b0b55f4bf040b304
  at: '2026-11-16T08:43:19+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: a write that OpenViking answers with a lock-timeout 409 twice and then 200 succeeds within the same event, with no failed event logged
  Fails when: the event fails, is NAKed, or the write is sent fewer than three times
- r2: a 409 that is not a lock timeout, and a lock timeout that persists past the retry limit, still fail the event
  Fails when: either case is reported as success or retried without bound
- r3: a retry waiting out its backoff holds no MaxInFlight slot
  Fails when: while one request sleeps between lock-conflict retries, another request cannot take the only slot
- r4: both roots pin ghcr.io/jasperhg90/ov-sync-consumer:v0.1.1, the module tests and vet pass, and the repo gates pass
  Fails when: either ov_sync_consumer_image line names another tag, or the module tests, vet or just pre_commit fail
- r5 (judgment): after the operator releases v0.1.1 and applies, a burst sync logs no 'event failed' line caused by a lock-timeout 409
  Fails when: the consumer log shows such a line during a sync
