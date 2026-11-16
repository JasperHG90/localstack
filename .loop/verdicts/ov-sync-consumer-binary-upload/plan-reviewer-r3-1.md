---
type: verdict
title: 'Verdict: ov-sync-consumer-binary-upload plan-reviewer round 3'
description: 'plan-reviewer verdict for round 3 of ov-sync-consumer-binary-upload: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:24:05+00:00'
slug: ov-sync-consumer-binary-upload
pass: plan-reviewer
round: 3
body_schema: verdict/1
---

## Summary

No open risk could break the plan. The extension-only rule now applies in
both Apply and catch-up, which closes p5. Spike 6 measures the ghost folder
that p6 asked about, and the plan changes the delete check for image folders
to match. The ghost folder does not confuse catch-up or the folder cleanup:
at worst it leaves a parent folder in place, which matches the plan's
accepted "empty folder stays visible" outcome.

## Checked

- Spike 6 stdout: after every delete path, `ls D` lists `D/diagram.png` as
  `dir`, `ls D/diagram.png` returns `[]`, and the file 404s. Cases A, B and
  C all show this. So the ghost is a directory entry with no children.
- catchup.go files(): a folder is any entry with `IsDir`, or any entry
  something else sits under. The ghost has `isDir: true`, so it goes into
  `dirs` and never into `have`. Walk queues it, gets `[]` back and adds
  nothing. Catch-up never treats the ghost as an unwanted file. When the
  image comes back, `D/name/name` is missing from `have`, so Apply uploads
  it, and spike 4 shows that an add into a leftover `to` folder stores the
  new bytes with no suffix.
- consumer.go remove/removeIfEmpty: for `D/name/name` the walk starts at
  `D/name`. `ls` returns `[]` (found), the recursive delete returns 200, and
  the plan's new check (an empty `ls D/name`) reports it removed. The walk
  then reaches D. `ls D` still lists the ghost, which is not a summary, so
  removeIfEmpty returns `(false, nil)` and the walk stops without an error.
  No errFolderLeft comes back, so no event retries forever and catch-up does
  not fail. A redelivered delete is also safe: the file delete 404s (counts
  as done) and the empty-folder check passes again.
- Delete in openviking.go already treats 404 as done.

## Findings

- p1, p2: resolved in round 2, because the temp folder and fs/mv are gone.
- p3: resolved in round 2 by the image-only scope.
- p4: resolved in round 2 by spikes 4 and 5.
- p5: resolved. The extension alone decides "image" in Apply and in
  catch-up. Catch-up spares the plain file at `U` while `U/base(U)` is
  wanted, and the upload deletes it. That removes the flip-flop and the
  migration-pass delete.
- p6: resolved. Spike 6 shows the folder stays listed for good, as an empty
  dir. The plan judges an image folder deleted when `ls D/name` is empty, and
  keeps the parent-listing check for text folders, which spike
  ov-sync-consumer/7 shows do leave the listing.

## Notes

Two things for the builder. Neither breaks the plan.

- A folder D that held an image is never removed after it empties, because
  the ghost `D/name` keeps it non-empty. The same goes for every folder
  above it. removeIfEmpty returns `(false, nil)` there, so this costs
  nothing at runtime. It only adds to the leftover folders the operator
  already accepted. The r5 test should not expect D to go away.
- "Delete a plain file at D/name if one is there" has to check that the
  entry is a file (for example `isDir` false in `ls D`) before it deletes.
  On every later upload `D/name` is already a folder (the live image or a
  ghost). A blind non-recursive DELETE of that folder was never measured on
  the real server, and a fake would not show what it does.
