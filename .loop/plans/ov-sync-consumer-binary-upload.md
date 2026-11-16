---
type: plan
title: 'Plan: ov-sync-consumer-binary-upload'
description: Upload images from ov-sync to OpenViking intact in its native per-resource folder layout, and skip other binary files instead of damaging them.
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

An object whose name ends in `.png`, `.jpg`, `.jpeg`, `.gif` or `.webp` is
uploaded the way OpenViking ingests a file,
which is also how ov-dash stores uploads: each one in its own folder named
after the file. For a key that maps to `D/name`, the image lands at
`D/name/name`:

1. `POST /api/v1/resources/temp_upload`, multipart field `file`, gives a
   `temp_file_id`.
2. `POST /api/v1/resources` with `temp_file_id`, `to: D/name`,
   `source_name: name`, `wait: true`. It creates missing parents, and a
   re-add with the same `to` replaces that folder, so a changed image
   overwrites the old one.

Before step 2 the consumer deletes a plain file at `D/name` if `ls D` lists
one there with `isDir` false (404 counts as done), which removes the damaged
copies the first sync wrote. A non-recursive delete of an image's folder is
refused with 412 and the image survives
(spike:ov-sync-consumer-binary-upload/8), and `isDir` is true for a live and
a leftover image folder alike, so only a plain file is ever deleted here.
The extension alone decides, in `Apply` and in catch-up alike, so the two
always agree on where an image lives; a `.png` holding text (a git LFS
pointer) is uploaded the same way, and the store succeeds even when the image
description fails (spike:ov-sync-consumer-binary-upload/1). Any other
object that is not valid UTF-8 is skipped with an INFO
`binary file skipped` line naming the key, because only PNG was measured and
OpenViking parses formats such as PDF instead of storing their bytes.

The per-key lock, deletes and catch-up all use the image's URI `D/name/name`,
which the key decides, so catch-up needs no S3 read to compute it. Catch-up
never removes a file at `U` while `U/base(U)` is wanted: that is the old
plain copy, and the image's upload deletes it.

Deleting the image removes `D/name/name`, then the folder `D/name` with
recursive=true. OpenViking answers 200, but `ls D` keeps listing `D/name` as
an empty folder for good (spike:ov-sync-consumer-binary-upload/6: nothing
inside, the file 404s, SeaweedFS shows a leaf). Folders `content/write`
created do leave the listing (spike:ov-sync-consumer/7). So for a folder an
image upload made, the delete counts as done when `ls D/name` is empty,
instead of checking that `ls D` no longer lists it. The empty folder stays
visible in ov-dash; a later upload to the same URI still works
(spike:ov-sync-consumer-binary-upload/4). Text keeps using `content/write`
and the existing folder check.

The image tag stays `v0.1.1`, not yet released, so this ships with the
per-key lock and the busy-folder change. Image links in the repo's markdown
point at `D/name`, which in OpenViking is a folder holding the image; the
operator accepted that layout.

Outcome: for a PNG event a fake OpenViking receives temp_upload then add
resource with `to = D/name`, and ends with the exact bytes at `D/name/name`
and siblings untouched; a changed PNG replaces it; a damaged plain file at
`D/name` is deleted first; a PDF is skipped with an INFO line and no write;
text still goes through `content/write` byte for byte; catch-up treats
`D/name/name` as the image's home and removes it when the bucket no longer
holds the image.

## Could invalidate this plan

- A deleted image's folder stays listed as an empty folder, so the
  existing "gone from the parent's ls" check would fail every image delete.
  spike:ov-sync-consumer-binary-upload/6 showed the folder stays listed;
  settled by spike:ov-sync-consumer-binary-upload/8: after the deletes,
  `ls D/name` is `[]` and the file 404s, and a re-add to the same `to` stores
  the new bytes with no `_1` folder.
- The request shapes come from a local v0.4.17.1-9 with stub models.
  Settled by spike:ov-sync-consumer-binary-upload/1 (`to = D/name` stores
  `D/name/name` byte for byte, and a re-add with the same `to` replaces that
  folder) and spike:ov-sync-consumer-binary-upload/4 (add resource creates
  missing parents). spike:ov-sync-consumer-binary-upload/3 and
  spike:ov-sync-consumer-binary-upload/5 tried an exact-URI route through a
  temp folder and fs/mv, which left hidden folders behind; the operator chose
  the native layout instead.
