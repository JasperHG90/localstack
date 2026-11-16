---
type: eval
title: 'Eval: ov-sync-consumer-binary-upload'
description: 'Definition of done for ov-sync-consumer-binary-upload: 7 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:16:02+00:00'
slug: ov-sync-consumer-binary-upload
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 1a4f7822bcef937e586d6b3fa98a64aba3bf0621ec0bb62701358d06c04d7226
  at: '2026-11-16T11:16:02+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: an event for a PNG that is not valid UTF-8 sends temp_upload, then add resource with to = D/name and source_name = name, and ends with the PNG's exact bytes at D/name/name and sibling files untouched
  Fails when: the fake OpenViking receives content/write for it, the calls or their fields differ, the stored bytes differ, or a sibling changes
- r2: a changed PNG replaces the one at D/name/name, and a plain file left at D/name by the old text write is deleted before the upload
  Fails when: D/name/name holds the old bytes, a second copy appears, or a file remains at D/name
- r3: a non-UTF-8 object that is not one of the image types is skipped with an INFO 'binary file skipped' line naming the key, and nothing is written
  Fails when: OpenViking receives any write or upload for it, or no such INFO line appears
- r4: a valid UTF-8 object with multi-byte characters still goes through content/write byte for byte, even with an image extension
  Fails when: it is uploaded as a resource, or the stored content differs from the object's bytes
- r5: catch-up counts D/name/name as the image's copy, uploads a missing image, and removes D/name/name and the emptied D/name folder when the bucket no longer holds the image
  Fails when: catch-up re-uploads an image that is present, misses a missing one, or leaves the image or its folder behind after the object is gone
- r6: the module tests and vet pass, and the repo gates pass
  Fails when: just -f applications/ov-sync-consumer/justfile test or just pre_commit exits non-zero
- r7 (judgment): after the operator releases v0.1.1 and applies, the three PNGs in docs/reference/architecture/ open in ov-dash at D/name/name and download with the same bytes as git, and no damaged plain copy remains at D/name
  Fails when: ov-dash reports a PNG as damaged, a download differs from git, or a plain file remains at D/name
