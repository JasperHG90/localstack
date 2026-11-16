---
type: eval
title: 'Eval: ov-sync-consumer-lock-conflict'
description: 'Definition of done for ov-sync-consumer-lock-conflict: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:04:50+00:00'
slug: ov-sync-consumer-lock-conflict
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 6cf45d3463435d5cf6e4e02b5b0ab2564e85b2a5b52a471c7ad7a0ef24e2b64f
  at: '2026-11-16T09:04:50+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: an event whose write OpenViking answers with a lock-timeout 409 is redelivered with the usual backoff and logs an INFO 'folder busy' line naming the URI, and no WARN
  Fails when: the event is acked, dead-lettered before its last try, NAKed with a different delay than Backoff(delivered), logs at WARN, or logs no INFO line with the URI
- r2: a 409 that is not a lock timeout still logs WARN 'event failed', and a lock-timeout 409 on the last allowed try still dead-letters
  Fails when: the other 409 logs at INFO, or the last-try lock 409 is not dead-lettered
- r3: a catch-up folder delete that hits a lock-timeout 409 logs it as folder busy instead of failing the pass with that error
  Fails when: the catch-up pass error or WARN log carries the lock-timeout 409
- r4: both roots pin ghcr.io/jasperhg90/ov-sync-consumer:v0.1.1, the module tests and vet pass, and the repo gates pass
  Fails when: either ov_sync_consumer_image line names another tag, or the module tests, vet or just pre_commit fail
- r5 (judgment): after the operator releases v0.1.1 and applies, a burst sync logs lock 409s only as INFO 'folder busy' lines
  Fails when: the consumer log shows a WARN 'event failed' line caused by a lock-timeout 409
