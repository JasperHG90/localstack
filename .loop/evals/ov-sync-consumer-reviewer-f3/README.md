---
type: eval
title: 'Eval: ov-sync-consumer-reviewer-f3'
description: 'Definition of done for ov-sync-consumer-reviewer-f3: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T08:01:39+00:00'
slug: ov-sync-consumer-reviewer-f3
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: fd8e481e08c7f9a84f59cce5d4f17d7962dea69e31de24bb42e93466ec863791
  at: '2026-11-16T08:01:39+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: two events for the same key handled by two workers at once leave OpenViking holding the object's latest content
  Fails when: a test that forces worker A to read v1, worker B to read and write v2, then A to write, ends with OpenViking holding v1
- r2: per-key serialization cannot deadlock against the tree lock: a burst of mixed writes, deletes and folder removals with catch-up running finishes
  Fails when: the burst test does not finish within its timeout
- r3: the module's full test suite and vet pass, and the repo gates pass
  Fails when: just -f applications/ov-sync-consumer/justfile test or just pre_commit exits non-zero
