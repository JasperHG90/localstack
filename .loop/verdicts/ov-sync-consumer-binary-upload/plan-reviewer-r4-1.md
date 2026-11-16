---
type: verdict
title: 'Verdict: ov-sync-consumer-binary-upload plan-reviewer round 4'
description: 'plan-reviewer verdict for round 4 of ov-sync-consumer-binary-upload: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:31:00+00:00'
slug: ov-sync-consumer-binary-upload
pass: plan-reviewer
round: 4
body_schema: verdict/1
---

## Summary

No open risk could break the plan. Round 3 left p1 to p6 resolved, and they
stay resolved. The plan changed in two places since round
3 (diff edef9d23..3fd42eb2), and spike 8 supports both.

## Checked

- Risk 1 now cites spike 8, which exited 0. Its stdout shows that after the
  file DELETE (200) and the recursive folder DELETE (200), `ls D/diagram.png`
  is 200 `[]` and the download is 404 (CHECK1 True). A re-add with the same
  `to` stores b.png byte for byte (sha ba47cb7b...), and neither `D` nor the
  folder gets a `_1` entry (CHECK2 True). That supports the plan's "empty
  `ls D/name` counts as done" check and the re-add-after-delete path.
- The pre-upload delete guard: stdout shows a non-recursive DELETE of a live
  image folder returns 412 FAILED_PRECONDITION and the image survives with
  the same sha. It also shows `ls D` reports the image folder as isDir=True
  in all three states and a content/write file as isDir=False. So the guard
  "delete `D/name` only when `ls D` lists it with isDir false" picks out
  exactly the damaged plain copies the first sync wrote, and it never sends a
  delete the server would refuse on a re-upload of a live image. Without the
  guard, every changed-image upload would hit the 412. The guard closes that
  gap rather than opening one.

## Findings

- p1, p2, p3, p4, p5, p6: resolved in earlier rounds (see round 3) and
  still resolved. The round 4 changes reopen none of them. No new findings.

## Notes

- When `D` does not exist yet (first upload to a new folder), `ls D` will
  likely 404. The guard must treat that as "nothing to delete". The tests
  will catch this quickly, and it does not threaten the approach.
- Spike 8 was one run with stub models on oidc only. That matches the
  evidence level the operator already accepted for spikes 1, 4 and 6.
