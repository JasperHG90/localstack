---
type: decision
title: "ADR 0030: ov-sync stores images in OpenViking per-file folders"
description: "Images reach OpenViking through temp_upload and add resource at D/name/name, its native layout, instead of an exact URI through a temp folder and fs/mv."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-16T11:48:59Z
status: stable
sources:
  - resource: "applications/ov-sync-consumer/internal/consumer/mapping.go"
  - resource: "applications/ov-sync-consumer/internal/consumer/consumer.go"
  - resource: "applications/ov-sync-consumer/internal/consumer/openviking.go"
---

# ADR 0030: ov-sync stores images in OpenViking per-file folders

## Context

The first ov-sync run sent every file to OpenViking's `content/write`, a text
API that takes the content as a JSON string. JSON turns each byte that is not
valid UTF-8 into U+FFFD, so the three PNGs in `docs/reference/architecture/`
landed damaged and ov-dash could not open them. OpenViking's way in for any
file is `temp_upload` then add resource, and add resource always puts a file
inside a folder of its own, with the summaries it writes about it.

## Decision

An image (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, by extension alone) is
uploaded with `temp_upload` and `POST /api/v1/resources` with
`to: D/name`, so it lands at `D/name/name`. A re-add with the same `to`
replaces it (spike:ov-sync-consumer-binary-upload/1). The consumer's lock,
deletes and catch-up all use `D/name/name`. Other non-UTF-8 files are skipped
with an INFO line, since OpenViking parses formats such as PDF rather than
storing their bytes.

Rejected: putting the image at its exact URI `D/name` by adding it into a
hidden temp folder, moving it with `fs/mv` and deleting the temp folder. It
kept markdown image links pointing at the real file
(spike:ov-sync-consumer-binary-upload/3), but the temp folder stayed listed
after its delete (spike:ov-sync-consumer-binary-upload/4,
spike:ov-sync-consumer-binary-upload/5), and the route needed its own crash
and race handling. The operator chose the native layout.

## Consequences

- A markdown image link such as `architecture/architecture.png` points at a
  folder in OpenViking that holds the image; ov-dash shows it one level down.
- Deleting an image leaves its folder listed in the parent as an empty folder
  for good (spike:ov-sync-consumer-binary-upload/6), so the consumer counts an
  image folder as deleted when `ls D/name` is empty, and the folders above it
  are never removed.
- A plain file left at `D/name` by the old text write is deleted before the
  upload, only when `ls D` lists it with `isDir` false
  (spike:ov-sync-consumer-binary-upload/8).
