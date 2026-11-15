---
type: verdict
title: 'Verdict: ov-sync-consumer reviewer round 2'
description: 'reviewer verdict for round 2 of ov-sync-consumer: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-15T21:48:00+00:00'
slug: ov-sync-consumer
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both findings sent back are fixed. Every OpenViking request now takes a slot
from one shared channel inside `send`, so workers and catch-up together stay
at or under POOL_SIZE. A slot is never held while waiting on the tree lock,
so the folder-delete lock cannot deadlock against the slots. Catch-up now
lists one folder per request, pages with node_limit, offset and has_more,
and walks the tree level by level. Its paging matches the real OpenViking
route. Two small nits remain (gofmt in main.go and one unwrapped doc line).
f3 is still open as deferred hardening.

## Checked

- `loopctl gate stamp` from the worktree: green, stamp
  2e0d600131be44e094e77f80e7dc4a12e97ef6fa9d480af228f202c14ce929f6, with
  pre_commit, cli_tests and rows r1 to r11 all passing.
- Deadlock: `send` gets the slot after any lock the caller holds and frees
  it once the body is read. Apply takes RLock and then a slot. remove takes
  RLock and a slot for the file delete, lets both go, then takes Lock and
  slots one request at a time. A goroutine waiting on the lock never holds a
  slot, so a slot holder is always in an HTTP request that ends (150 s client
  timeout). Neither path takes the RWMutex twice. Catch-up calls Apply and
  remove only after Walk returns, so it holds no lock while it walks.
- Slot setup: `sync.Once` builds the channel on first use. MaxInFlight is
  set to `pool` in main.go. The send waits on ctx, so shutdown is not stuck
  on a full channel.
- Real route: read `server/routers/filesystem.py` `ls`,
  `service/fs_service.py` `ls`, and `storage/viking_fs/_ops.py`
  `_ls_browsable_items`. The server fetches node_limit+1 and sets has_more
  when there is more. Offset skips entries after the hidden filter, which
  show_all_hidden turns off, so the client's `offset=len(entries)` is right.
  The envelope's `has_more` sits next to `result` (`ListingResponse`), which
  matches `envelope.HasMore`. The fake's ls does the same: sorted, offset,
  limit, has_more, 404 for a missing folder, and recursive capped at three
  levels.
- r8 / TestConsumerPoolBound: CatchUp now runs in a loop during the
  200-event burst. It has 40 stale files, so its listings, deletes and
  folder removals race the workers. The test fails if the peak measured
  inside the fake goes over Pool, and it waits for the deletes to finish, so
  the catch-up traffic really overlaps the burst. Without the shared slots
  the peak would go over 4.
- TestCatchUpListsWholeTree: 1200 files in one folder (above the 1000 page
  size) and one file five levels deep. It fails on any write or delete. A
  client that dropped has_more or relied on recursive ls would rewrite files
  and fail the test.
- Docs: the components page (lines 93 to 97, 121 to 125, invariant table),
  the jobspec comment, and the Consumer.Pool and OpenViking.MaxInFlight
  docstrings now say what the code does.

## Findings

- f1 resolved: shared slots in `OpenViking.send`
  (internal/consumer/openviking.go), covered by the extended
  TestConsumerPoolBound.
- f2 resolved: `List` pages and `Walk` lists level by level
  (internal/consumer/openviking.go), and catchup.go uses `Walk`. Covered by
  TestCatchUpListsWholeTree.
- f3 open, not blocking: not touched in this round. It moved to the stub
  ticket ov-sync-consumer-reviewer-f3.
- f4 open, nit: `gofmt -l` (the prek-cached go 1.27.4 toolchain) lists
  main.go. Adding `MaxInFlight` widened the field column, and `URL:` and
  `TokenFile:` were not realigned. No gate runs gofmt, so the stamp stays
  green. Fix it with `gofmt -w main.go`.
- f5 open, nit: .okf/components/ov-sync-consumer.md line 97 is 124
  characters of prose. The rest of the page wraps at 80.

## Notes

If a file is deleted between two pages, the offset paging can skip an entry
in that folder. At worst the next pass makes one extra write or misses one
delete, so this is not a finding.
