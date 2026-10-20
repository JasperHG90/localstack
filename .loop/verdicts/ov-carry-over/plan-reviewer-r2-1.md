---
type: verdict
title: 'Verdict: ov-carry-over plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ov-carry-over: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T15:19:32+00:00'
slug: ov-carry-over
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Round 2, fail. p1 and p2 are resolved. One new risk, p3: as written, a
re-run of the copy job overwrites sidecars that the re-index step and the
live instance rewrote, and its hash check then fails. This is a fix to the
copy flags and the check, not a rethink. No split needed.

## Checked

- p1: the plan leaves rewritten sidecars out of the hash check, checks them
  on their own, and requires no `blog-scraper/` text under `blogs/`. It also
  makes the rewrite skip existing keys. Resolved.
- p2: spike:ov-carry-over/4 (exit 0, stdout read). Every re-index mode
  leaves the png with 0 level-2 rows. Copying the old row gives 1 row,
  find returns the png, the row survives a later vectors_only, and no VLM
  call is made. The plan copies the rows after the re-index, which is the
  order the spike tested. Resolved.
- Table shape and row identity, read in the v0.4.17.1-9 image. Each
  `ov_context` table comes from the same collection schema
  (`openviking/storage/collection_schemas.py`), so the columns match when
  the old schema was made by the same adapter. The primary key `id` is
  `md5(account_id + ":" + uri)` (`_seed_uri_for_id`). Deletes go by `uri`
  filter (`remove_by_uri`, `delete_uris`), not by a recomputed id. Account
  `lab` and user `jasper` are the same in both instances, so
  `account_id`/`owner_user_id` carry over unchanged.
- Embedder: `embark/embedding` at 384 since d2cf84d (2026-09-09). embark
  later moved from granite fp32 to a trimmed fp16 build of the same model
  (ee61fc5). The two builds should give near-equal vectors. The plan's
  per-image find check would show any drift.

## Findings

- p1 (resolved): rewritten sidecars are out of the hash check and checked
  on their own.
- p2 (resolved): the old image rows are copied after the re-index, as
  spike:ov-carry-over/4 tested.
- p3 (open): a re-run overwrites regenerated and live sidecars under clips/,
  leo/ and blogs/, then fails its own hash check. Make every copy skip
  existing keys, and limit the hash check to what the target keeps
  unchanged.

## Notes

Build details, not findings:


- For the 30 blog-scraper images whose URI is rewritten, compute the new
  `id` as `md5('lab:' || new_uri)`, as OpenViking's own
  `update_uri_mapping` does, rather than copying the old id. A stale id
  does not break search or delete-by-URI, but a later re-ingest would add a
  second row.
- If the blog-scraper sidecars go through `rclone copy` before the
  `cat | sed | rcat` rewrite, the rewrite's skip-existing rule skips them
  all. The `no blog-scraper/ text under blogs/` check would catch it.
- If Hermes runs the old skill between the cutover and this ticket, it
  writes to `viking://user/jasper/resources/blog-scraper/` in the new
  instance. That trips the outcome's "only what ov-fresh-instance created"
  check.
