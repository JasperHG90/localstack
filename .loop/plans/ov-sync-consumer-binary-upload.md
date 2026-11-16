---
type: plan
title: 'Plan: ov-sync-consumer-binary-upload'
description: Upload binary files from ov-sync to their exact OpenViking URI intact, through temp_upload, add resource into a temp folder and fs/mv.
tags:
- plan
slug: ov-sync-consumer-binary-upload
status: draft
epic: null
depends_on: []
priority: null
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:33:12+00:00'
---

# ov-sync-consumer-binary-upload

Relayed from: none

## Intent

`Apply` in `applications/ov-sync-consumer/internal/consumer/consumer.go`
writes every object with `content/write` as `string(body)` inside JSON, and
JSON turns each byte that is not valid UTF-8 into U+FFFD. The first sync
stored the three PNGs in `docs/reference/architecture/` damaged
(`architecture.drawio.png`: 585,583 bytes in git, 956 KB in OpenViking, and
ov-dash cannot open it).

An object that is not valid UTF-8 goes through the route
spike:ov-sync-consumer-binary-upload/3 proved on v0.4.17.1-9, in
`openviking.go`:

1. `POST /api/v1/resources/temp_upload`, multipart field `file`, gives a
   `temp_file_id`.
2. `POST /api/v1/resources` with `temp_file_id`, `to` set to a hidden temp
   folder `<parent>/.ovsync-upload-<random>`, `source_name` the file's name,
   `wait: true`.
3. `POST /api/v1/fs/mv` from `<temp>/<name>` to the file's URI. It overwrites
   an existing file in place with no gap.
4. Delete the temp folder with the existing empty-folder guard
   (`removeIfEmpty`: recursive only when ls shows nothing but the two
   summaries).

Text keeps using `content/write`. Deletes and catch-up need no change: the
binary sits at the same URI a text file would. A temp folder left behind by
a crash between steps holds a file catch-up does not want, so catch-up's
existing remove path deletes it.

`add resource` (`to` = the file URI or its folder, or `parent`) cannot do
this alone: it stores `D/name/name`, `D/stem/name`, or replaces all of D
(spike:ov-sync-consumer-binary-upload/1, spike:ov-sync-consumer-binary-upload/2).

The image tag stays `v0.1.1`, not yet released, so this ships with the
per-key lock and the busy-folder change. After the operator releases and
applies, the next push that touches the three PNGs, or a manual re-upload of
them to the bucket, replaces the damaged copies.

Outcome: a fake OpenViking that implements the four calls receives them in
order for a binary object and ends with the exact bytes at the file's URI,
sibling files untouched and no temp folder left; text still goes through
`content/write` byte for byte; a temp folder left by a failed upload is
removed by catch-up.

## Could invalidate this plan

- The request shapes come from a local v0.4.17.1-9 with stub models.
  Settled by spike:ov-sync-consumer-binary-upload/3 (exact URI, siblings
  kept, overwrite in place without a gap, temp folder removed, file
  indexed), with spike:ov-sync-consumer-binary-upload/1 and
  spike:ov-sync-consumer-binary-upload/2 ruling out `add resource` alone.
