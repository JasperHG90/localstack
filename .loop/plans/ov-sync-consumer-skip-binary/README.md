---
type: plan
title: 'Plan: ov-sync-consumer-skip-binary'
description: Stop the consumer damaging binary files by skipping objects that are not valid UTF-8, shipped in the unreleased v0.1.1.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:32:53+00:00'
slug: ov-sync-consumer-skip-binary
epic: null
depends_on: []
priority: null
---

# ov-sync-consumer-skip-binary

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none

## Intent

`Apply` in `applications/ov-sync-consumer/internal/consumer/consumer.go`
sends every object to OpenViking's `content/write` as `string(body)` inside
JSON. Go's JSON encoder replaces each byte that is not valid UTF-8 with
U+FFFD, so binary files land damaged: the operator found
`docs/reference/architecture/architecture.drawio.png` (585,583 bytes in git)
stored as 956 KB that ov-dash cannot open. Three files in `docs/` and `.okf/`
are binary today, all PNGs in that folder.

`Apply` checks the body with `utf8.Valid` before writing. An object that is
not valid UTF-8 is not written; the consumer logs it at INFO as
`binary file skipped` with the key, and the event is acked as handled.
Catch-up's repair of a missing file goes through `Apply`, so it skips the
same files without failing the pass. Uploading binaries properly is the stub
`ov-sync-consumer-binary-upload`. The image tag stays at `v0.1.1`, which is
not released yet, so this ships with the per-key lock and the busy-folder
change.

Outcome: a test that puts a PNG-like non-UTF-8 object in the fake bucket sees
no write to OpenViking, an INFO `binary file skipped` line and an acked
event; a UTF-8 file with multi-byte characters is still written byte for
byte; catch-up over a bucket holding a binary file returns no error and
writes nothing for it.

## Could invalidate this plan

- none
