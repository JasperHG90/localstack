---
type: verdict
title: 'Verdict: devcontainer-ovsync reviewer round 2'
description: 'reviewer verdict for round 2 of devcontainer-ovsync: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-28T10:30:41+00:00'
slug: devcontainer-ovsync
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Narrow round. f1 is fixed. The ov/ovx prerequisite now links the ovx README at
the ovx-v0.4.0 tag. That README covers installing ovx, says it needs the ov
CLI, and shows how to create a profile (`ovx -n`) and log in with `--bind`.
The VAULT_ADDR bullet links log-in-to-vault.md, which exists. The fix broke
nothing it touched, so the change passes.

## Checked

- Gates: `loopctl gate stamp` from the worktree came back green
  (6bf5a48ca19e32e13c671f42be578687c65d46269c37baa1aa27a293d14c8a88). It passed
  pre_commit, cli_tests and eval rows r1 to r4. r4 includes test_how_to_skeleton.
- Links: tag ovx-v0.4.0 exists in the openviking_extensions clone, and
  packages/ovx/README.md exists at that tag with Install and Use sections.
  docs/how-to/log-in-to-vault.md, call-openviking-from-the-cli.md,
  ../reference/openviking.md and ../explanation/openviking-identity.md all
  resolve.
- Step 3 rewording: Docker refuses a bind mount whose source is missing when
  it creates the container, not when it builds the image, so "Creating the
  container fails" is accurate.
- The page still has the four how-to sections in order, with Step 1 to Step 5.

## Findings

- f1: resolved in
  docs/how-to/sync-a-folder-to-openviking-from-the-devcontainer.md, in the
  Prerequisites bullets, as described above.

## Notes

The ovx README at ovx-v0.4.0 shows an install command pinned to ovx-v0.3.0.
That is an upstream README issue, not this ticket's.
