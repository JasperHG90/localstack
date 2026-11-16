---
type: verdict
title: 'Verdict: ov-sync-consumer-binary-upload reviewer round 2'
description: 'reviewer verdict for round 2 of ov-sync-consumer-binary-upload: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:54:40+00:00'
slug: ov-sync-consumer-binary-upload
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 is fixed. ADR 0030 records the native per-file folder layout, the
rejected temp-folder and fs/mv route, and the consequences. The component
page links it. Its claims match the spikes and the code. Code is unchanged
since round 1, so the label is pass.

## Checked

- Gates: `loopctl gate stamp` from the worktree passed: pre_commit,
  cli_tests and eval rows r1-r6, stamp
  aa1752f3b59713572f24e1d25c65bf4dff63ed38043684204b2b984fb900d900.
- `kmctl check` in the worktree: "all checks passed".
- ADR 0030 against the spikes: the add with `to: D/name` stores at
  `D/name/name` (spike 1). A re-add replaces it (spike 1, also spike 8
  on a ghost folder). The temp route reached the exact URI (spike 3). The
  temp folder stayed listed after its recursive delete (spikes 4 and 5),
  and the operator then chose the native layout (spikes 4 and 5 say so).
  A deleted image leaves an empty folder listed in `ls D` for good, so
  only `ls D/name` tells a ghost from a live one (spikes 6 and 8). A
  non-recursive delete of an image folder gets 412, and `ls D` reports a
  content/write file as isDir false (spike 8), which backs the guard.
- ADR 0030 against the code: the extension list matches mapping.go:70.
  The three PNGs in `docs/reference/architecture/` match `git ls-files`.
  The PDF reason for skipping other binaries comes from the plan.
- Component page: the new link to ADR 0030 resolves, and the decisions
  index lists the record.

## Findings

- f1 (resolved): `.okf/decisions/0030-ov-sync-stores-images-in-openviking-per-file-folders.md`
  holds the choice, the rejected route with spikes 3-5, and the
  consequences. `.okf/components/ov-sync-consumer.md` links it from the
  image bullet.

## Notes

- The ADR does not mention the `parent=D` shape that spike 2 ruled out
  (it wraps each file in a stem folder and never overwrites). The record
  is accurate without it. Adding a line would only make it more complete.
