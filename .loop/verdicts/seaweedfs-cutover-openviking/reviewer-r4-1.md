---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking reviewer round 4'
description: 'reviewer verdict for round 4 of seaweedfs-cutover-openviking: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T07:41:14+00:00'
slug: seaweedfs-cutover-openviking
pass: reviewer
round: 4
body_schema: verdict/1
---

## Summary

f5 is fixed. The OpenViking paragraph in orangepi4a.md now follows the whole
"What dials it by literal address" list, and the HAProxy bullet is back in
that list. The optional note from round 3 is also handled: exit 3 on the
component page now covers a failed SeaweedFS listing. Gates are green. f1 to
f4 stay resolved. Nothing is left open.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, pass r2, stamp green
  d2d304f6b55fab4fbded8f6c26b78fd862c3169cd5b9b89316b4b8b54e06af23.
- .okf/nodes/orangepi4a.md lines 78 to 95: four bullets in one list, ending
  with HAProxy and Prometheus. The OpenViking paragraph comes after the list.
- .okf/components/gcs-backups.md lines 127 to 132: "3 a directory missing on
  SeaweedFS or its listing". This matches restore-s3.hcl, where the
  `lsf ... "$dst" > /tmp/dst-dirs || exit 3` line exits 3. Exits 1, 2, 4 and
  5 still match the script. The rewrapped lines are within 80 columns. The one
  long line at line 181 was there before this ticket and is not in the diff.
- restore-s3.hcl is unchanged since round 3. The case allowlist (exit 5) and
  the file-backed listings with their own exit guards (f1, f2) are still in
  place.

## Findings

- f1 (resolved): the listings still write to files, and each has its own exit
  guard.
- f2 (resolved): the case allowlist still exits 5 on any other bucket.
- f3 (resolved): exit 5 is still in the reference table and on the component
  page.
- f4 (resolved): no change since round 3, and the .okf pages still cover both
  cutovers.
- f5 (resolved): the paragraph now sits below the last bullet in
  .okf/nodes/orangepi4a.md.
