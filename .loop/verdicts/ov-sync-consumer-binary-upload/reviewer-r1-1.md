---
type: verdict
title: 'Verdict: ov-sync-consumer-binary-upload reviewer round 1'
description: 'reviewer verdict for round 1 of ov-sync-consumer-binary-upload: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:48:36+00:00'
slug: ov-sync-consumer-binary-upload
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says. Images resolve to D/name/name and go up
through temp_upload and an add resource with `to: D/name`. Other non-UTF-8
objects are skipped with an INFO line. Text still goes through content/write.
Deleting an image treats an empty `ls D/name` as gone. Catch-up spares the old
plain copy while its image is wanted. Lock order holds and the tests check
the eval rows' fails_when conditions. The only finding is a missing decision
record, which a plain fix covers, so the label is fix.

## Checked

- Gates: `loopctl gate stamp` from the worktree passed: pre_commit,
  cli_tests and eval rows r1-r6 all passed, stamp
  4772618db8416571b23548c9d6ed3035de6e2390702206baf27c0cbc890e4a2c. I also
  ran `just -f applications/ov-sync-consumer/justfile test` (vet plus the
  full module, ok) and test-one for each of the five named tests (ok).
- Lock order: Apply takes the key, then Limit, the S3 read and tree.RLock.
  upload makes all of its ls, delete, temp_upload and add calls under that
  RLock and takes no second key. remove still takes RLock, releases it, then
  takes Lock, with no nesting. Catch-up takes one key at a time, releases it,
  and calls Apply without holding a key. Each OV request holds a MaxInFlight
  slot only for itself. temp_upload goes through `call`, so it takes a slot
  and maps 409s.
- Resolve's effect: a delete event for an image becomes remove(D/name/name).
  removeIfEmpty(D/name, image=true) checks `ls D/name` after the recursive
  delete, then moves up to D, where the ghost folder stops the walk. A
  replayed delete on a ghost or a missing folder ends cleanly. Catch-up's
  want holds D/name/name and have gets it from Walk, while ghost folders are
  dirs and never count as files. The old plain copy D/name: the want loop
  runs Apply first, which deletes it, and the guard keeps the stale have
  from removing it. Once the image leaves the bucket, the guard no longer
  fires and catch-up removes the copy like any unwanted file. An image at the
  mapped root works, since the loop covers root/name.png.
- isImageHome: it needs an image extension, so no text path qualifies.
  Old-sync text at X/y.png/y.png would only switch the folder check to the
  `ls D/name` form, which is harmless. Git cannot hold a file and a folder
  with the same name, so image homes cannot collide with real paths.
- Fake fidelity against spikes 1, 4, 6 and 8: `to` is the resource's own
  folder and a re-add replaces it (1). Missing parents are created (4). A
  recursive delete empties an image folder, but the folder stays in `ls D`
  as an isDir entry (6, 8). A non-recursive delete of the folder gets 412
  (8). A content/write file reports isDir false (8). The fake does not cover
  for the consumer: an add over a plain file at `to` leaves that file in
  place, so r2 would fail if the consumer skipped its delete. Without the
  guard, the catch-up removal would get 412 and fail r5, which matches the
  builder's mutation claim.
- Eval rows: r1 checks no content/write, the temp_upload bytes and filename,
  the add fields, call order, the stored bytes and unchanged siblings, plus
  case-insensitive extensions and errLockBusy through the add. r2 checks
  that one non-recursive delete removes the plain copy, that a re-upload
  replaces the image with no further delete, and the exact contents of the
  folder. r3 checks zero OV requests and one INFO line naming the key. r4
  checks no upload and content/write of multi-byte text byte for byte. r5
  checks present, missing, migrated and gone images, no forbidden deletes,
  no violations, a ghost folder that does not fail the pass, and an
  idempotent second pass. r7 is an operator judgment for after release.
- Errors: upload wraps delete and Upload errors with %w, call wraps
  errLockBusy, and remove wraps removeIfEmpty errors as errFolderLeft, so
  skipBusy and handle still sort them. The add's `timeout: 120` is the same
  as Write's and stays under the 150 s client timeout in main.go.
- Docs: I read the .okf component diff and found it accurate. No docs/ page
  describes the byte handling.

## Findings

- f1 (docs, non-blocking): the native-layout choice and the exact-URI route
  it replaced need a decision record under `.okf/decisions/` (`kmctl new
  decision`). Link it from the component page.

## Notes

- Catch-up re-runs Apply on every non-image binary every pass, because
  OpenViking never holds a copy of one. Each run costs an S3 GET, a rate
  token and an INFO line. The repo has no such file today (only the five
  PNGs fail UTF-8), so I am not raising it.
- If an image leaves the bucket while its old plain copy is still at D/name,
  the event path runs `ls` on that plain file. The fake answers 404. The
  real server's answer was not measured. The worst case is an errFolderLeft
  retry, and catch-up removes the copy anyway.
