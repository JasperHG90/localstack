---
type: eval
title: 'Eval: ov-sync-consumer-skip-binary'
description: 'Definition of done for ov-sync-consumer-skip-binary: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:33:15+00:00'
slug: ov-sync-consumer-skip-binary
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: fd09e44e2d16e3ce2b1efba513781cd483b9723c1f67e488a2bc16b2518081fb
  at: '2026-11-16T09:33:15+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: an event for an object that is not valid UTF-8 writes nothing to OpenViking, logs an INFO 'binary file skipped' line naming the key, and is acked without redelivery or a dead letter
  Fails when: OpenViking receives a write for it, no such INFO line appears, or the event is redelivered or dead-lettered
- r2: a valid UTF-8 object with multi-byte characters is still written to OpenViking byte for byte
  Fails when: the stored content differs from the object's bytes
- r3: a catch-up pass over a bucket holding a binary object returns no error and writes nothing for it
  Fails when: the pass returns an error or OpenViking receives a write for the binary object
- r4: the module tests and vet pass, and the repo gates pass
  Fails when: just -f applications/ov-sync-consumer/justfile test or just pre_commit exits non-zero
