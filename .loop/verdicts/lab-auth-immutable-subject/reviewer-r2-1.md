---
type: verdict
title: 'Verdict: lab-auth-immutable-subject reviewer round 2'
description: 'reviewer verdict for round 2 of lab-auth-immutable-subject: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-18T13:33:29+00:00'
slug: lab-auth-immutable-subject
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Narrow round 2. f1 is resolved: the CI bullet is gone from the summary's
Open gaps list, so the list no longer names a gap that is closed. The fix
touched nothing else.

## Checked

- `git diff main -- .okf/summary.md` in the worktree: the only change is
  the removal of the three-line CI/ADR 0027 bullet. The surrounding list
  (SeaweedFS, OpenViking, ov-sync, Postgres, manifesto) is intact and reads
  correctly.
- `kmctl check` in the worktree: "all checks passed".
- `loopctl gate stamp` could not be re-run in this session; the
  environment's permission layer denied the command, so no stamp result is
  quoted here.

## Findings

- f1: resolved. `.okf/summary.md` no longer carries the CI bullet under
  Open gaps; ADR 0027 and 0031 stay reachable through the decisions index.
  No new issue introduced.
