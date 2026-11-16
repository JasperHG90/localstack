---
type: eval
title: 'Eval: ov-sync-consumer-binary-upload'
description: 'Definition of done for ov-sync-consumer-binary-upload: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:52:30+00:00'
slug: ov-sync-consumer-binary-upload
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 4cc154f3e80ff9e0d5f9367a4f75cb51e59b7daa8f5e947c3d51120b4909246e
  at: '2026-11-16T09:52:30+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: an event for an object that is not valid UTF-8 uploads it through temp_upload, add resource into a .ovsync-upload- temp folder under the file's parent, fs/mv to the file's URI and a delete of the temp folder, ending with the object's exact bytes at its URI and no temp folder
  Fails when: the fake OpenViking receives content/write for it, the calls come in another order, the stored bytes differ, a sibling file changes, or a .ovsync-upload- folder remains
- r2: uploading a changed binary to a URI that already holds one replaces it with the new bytes
  Fails when: the URI still holds the old bytes or a second copy appears
- r3: a valid UTF-8 object with multi-byte characters still goes through content/write byte for byte
  Fails when: it is uploaded as a resource, or the stored content differs from the object's bytes
- r4: a catch-up pass removes a .ovsync-upload- temp folder a failed upload left behind
  Fails when: the temp folder or its file is still listed after the pass
- r5: the module tests and vet pass, and the repo gates pass
  Fails when: just -f applications/ov-sync-consumer/justfile test or just pre_commit exits non-zero
- r6 (judgment): after the operator releases v0.1.1, applies, and the three PNGs are synced again, each opens in ov-dash and downloads with the same bytes as git
  Fails when: ov-dash still reports a PNG as damaged or a download differs from git
