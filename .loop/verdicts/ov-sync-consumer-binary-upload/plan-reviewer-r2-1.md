---
type: verdict
title: 'Verdict: ov-sync-consumer-binary-upload plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ov-sync-consumer-binary-upload: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:18:08+00:00'
slug: ov-sync-consumer-binary-upload
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

The native layout drops the temp folder, so round 1's p1, p2 and p4 are
resolved and p3 is answered by the image-only scope. Spike evidence supports
the upload itself: exact bytes at D/name/name, missing parents created, a
re-add with the same `to` replacing rather than nesting. Two risks remain,
both on the catch-up and delete side. Catch-up and Apply use different rules
for "image", and that mismatch, combined with the stale have snapshot,
deletes the wrong copy (p5). The folder cleanup after an image delete may not
work on the real server, given spikes 4 and 5 (p6). Both call for revision,
not a rethink.

## Checked

- Spike 1 stdout: `to=D, source_name=n` stores D/n. A second add with the
  same `to=D` replaced D's contents with no `_1` suffix and no nesting.
  `to=E` (E ending in diagram.png) stored E/diagram.png. So `to=D/name,
  source_name=name` gives D/name/name, and a same-`to` re-add replaces it.
  Spike 4, round 3 adds again into the same leftover `to` folder and gets the
  new bytes at to/name, with no suffix. Spike 3 shows that adding to a
  subfolder of D keeps D's siblings (notes.md survived). I accept this as
  answering the replace-not-nest question and the sibling-safety question for
  `to=D/name`.
- Spikes 4 and 5: add creates missing parents (p4). Their exit-1 cause is a
  recursive delete that leaves the add-resource folder listed (p6).
- catchup.go: want is built from Map.Resolve(key) alone, so D/name/name can
  be computed from the key and extension without reading S3. files() marks
  D/name as a folder (IsDir, and a parent of other entries), keeps D/name/name
  as a file, and drops D/name/.abstract.md and .overview.md through
  isSummary. So the have side does see the image. Both loops work from one
  snapshot taken before any Apply (p5).
- consumer.go: Apply locks the Resolve URI, takes tree.RLock and writes.
  remove deletes the file, then climbs from parent(uri), so deleting
  D/name/name reaches removeIfEmpty(D/name) and then D. removeIfEmpty treats
  "still listed after delete" as an error, which becomes errFolderLeft (p6).
- openviking.go: do() marshals JSON only. temp_upload needs a multipart
  sender. That is a build detail, and the folder-lock 409 mapping can be
  reused there.

## Findings

- p1, p2: resolved, because the temp folder and fs/mv are gone.
- p3: resolved by the image-only scope. JPEG, GIF and WebP were not measured,
  but they take the same image parser path as PNG (`content_type: image`),
  and a build-time test is the quicker check.
- p4: resolved by spikes 4 and 5.
- p5: the extension-only rule in catch-up against Apply's UTF-8 rule, plus
  the stale have snapshot. This makes a valid-UTF-8 .png flip between present
  and deleted on every pass. On the migration pass it also deletes D/name
  after Apply has turned it into the image's folder.
- p6: spikes 4 and 5 show recursive delete leaving an add-resource folder
  listed. If that is the normal case, removeIfEmpty fails on every image
  delete. Spike it before building.

## Notes

The ticket is not too large to split. Both findings sit in one place: how
deletes and catch-up treat the image's folder.
