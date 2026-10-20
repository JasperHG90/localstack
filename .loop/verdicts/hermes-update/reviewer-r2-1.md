---
type: verdict
title: 'Verdict: hermes-update reviewer round 2'
description: 'reviewer verdict for round 2 of hermes-update: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T11:18:50+00:00'
slug: hermes-update
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round 1 findings are fixed. The log entry records the staged memex model
change, and the r1 test now fails when the plugin download points at a branch.
Nothing in the fixes broke anything else.

## Checked

- Gates: `loopctl gate stamp` from the worktree passed `pre_commit`,
  `cli_tests` and eval row r1, and stamped green at
  e48bcb220c12674b191ea86efc9b0083c9dcf54d8ee42fbcb2e3d3be46566d0a.
- f1: `resource "nomad_job" "memex"` is commented out at
  `deployments/applications/services.tf:839`, and it is the only reference to
  `services/memex.hcl` in any `.tf` file. Nothing live reads the edited
  jobspec, so the edit causes no 403 and no drift. My round 1 note that live
  memex was failing was wrong. The new `.okf/log.md` entry says exactly this.
- f2: I copied the deployments tree and the test to the scratchpad, changed
  the codeload URL to `tar.gz/main`, and ran the test against the copy.
  `test_openviking_plugin_is_copied_in_pinned` failed at line 28 and the other
  three passed. The tar member assertion also uses the pinned variable.

## Findings

- f1: resolved in `.okf/log.md` (the 2026-10-20 hermes-update entry).
- f2: resolved in `cli/tests/test_hermes_version.py:28-29`, and the mutation
  check above shows the test fails.
