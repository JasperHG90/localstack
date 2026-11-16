---
type: verdict
title: 'Verdict: ov-sync-consumer-skip-binary plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-sync-consumer-skip-binary: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T09:34:12+00:00'
slug: ov-sync-consumer-skip-binary
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. The approach matches the failure, it
cannot make catch-up loop, and the existing damaged copies are covered by the
stub ticket ov-sync-consumer-binary-upload.

## Checked

- utf8.Valid is the right test. encoding/json replaces invalid UTF-8 with
  U+FFFD, so the check matches the damage exactly. A PNG starts with 0x89,
  which can never begin a UTF-8 sequence, so every PNG is caught. An empty
  object and a UTF-8 BOM are valid UTF-8 and get written as before. A Latin-1
  or UTF-16 text file would now be skipped, where before it was written with
  replacement characters. That loses nothing the old path kept intact, and
  the operator found only three non-UTF-8 tracked files under docs/ and
  .okf/, all PNGs.
- Catch-up cannot loop. It calls Apply only for a bucket file missing from
  OpenViking (catchup.go, `!have[uri]`), once per pass, and joins the
  results. A skip returns nil, so the pass succeeds. Each pass costs one GET
  and one INFO line for each binary missing from OpenViking. The three
  damaged PNGs are already present, so today that cost is zero.
- Damaged copies already in OpenViking stay after this change: catch-up
  compares only presence, and a skipped event writes nothing. Replacing them
  is in scope for ov-sync-consumer-binary-upload, which depends on this
  ticket. Deleting a binary from the bucket still goes through the NoSuchKey
  path to remove, so a deleted file's copy is still cleaned up. This is a
  scope split, not a gap.
- Write goes through `do`, which calls json.Marshal on the body
  (openviking.go), so the root-cause claim holds.
- Both roots pin v0.1.1 (services.tf in deployments/applications and
  deployments/infrastructure).

## Findings

None.
