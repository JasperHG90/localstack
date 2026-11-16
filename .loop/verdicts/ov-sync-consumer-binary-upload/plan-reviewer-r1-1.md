---
type: verdict
title: 'Verdict: ov-sync-consumer-binary-upload plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-sync-consumer-binary-upload: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T09:55:07+00:00'
slug: ov-sync-consumer-binary-upload
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The route spike 3 found does work for PNGs beside an existing sibling, and
the lock ordering holds. But the temp folder's lifecycle has two holes: a
leftover after the mv is never cleaned (p1), and catch-up can delete a live
upload (p2). The evidence also covers less than the plan claims: only PNG,
not every format that is not UTF-8 (p3), and only a parent that already
exists (p4). All four are revisions, not a rethink.

## Checked

- Spikes 1 to 3: README outcomes, stdout and run.json. Spike 3 exited 0. It
  showed the exact sha256 at the target URI, siblings kept, mv overwriting
  with no gap (111 polls), one VLM call per upload and none on the mv, and
  the temp folder removed by a recursive delete whose response re-summarized
  D.
- consumer.go: Apply takes the key, then tree.RLock. remove and removeIfEmpty
  take tree.Lock after RUnlock. The upload can follow the same order (key,
  RLock for steps 1 to 3, RUnlock, then Lock for removeIfEmpty on the temp
  folder) and does not break the rule "key before tree, never two keys". A
  concurrent sibling delete that climbs to D sees the temp folder and stops.
- openviking.go: do() turns a 409 whose message says "lock acquire timed
  out" into errLockBusy for any path. So add, mv and the temp delete get the
  existing busy handling if they go through do(): nak with backoff for
  events, skipBusy in catch-up. List passes show_all_hidden=true, so Walk
  descends into dot folders.
- catchup.go: files() keeps <temp>/<name> as an unwanted file, so a leftover
  from before the mv is removed by remove(), which climbs and deletes the
  temp folder. A summaries-only folder is not seen (p1).
- mapping.go: a repository path would collide only if it held the same
  random .ovsync-upload- name. I found no mapping risk.
- The repository holds 5 non-UTF-8 files, all PNG. The action is meant for
  other repositories too (p3).

## Findings

- p1: a temp folder left after the mv is never cleaned, by catch-up or by
  redelivery.
- p2: catch-up locks the temp URI rather than the target, so it can delete an
  in-flight upload's file between add and mv.
- p3: the scope is wider than the evidence. Formats that add resource parses
  may not land at <temp>/<name>.
- p4: add resource with `to=` under a missing parent was never tried.

## Notes

Cost: each binary runs one VLM call on the image plus a summary of the temp
folder, and the temp delete then re-summarizes D. That is about two to three
times a text write, which is acceptable for a handful of images. A retry
after a 409 on the mv repeats the VLM call. The folder-lock 409 will likely
serialize binaries in one folder (the three PNGs), the same way text writes
already are serialized, and backoff converges.
