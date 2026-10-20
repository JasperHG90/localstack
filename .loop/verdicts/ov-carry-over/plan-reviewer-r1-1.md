---
type: verdict
title: 'Verdict: ov-carry-over plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-carry-over: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T14:49:04+00:00'
slug: ov-carry-over
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Round 1, fail. The plan's approach holds: spikes 1 and 3 answer both listed
risks. Two new risks need a revised plan: the sidecar rewrite contradicts the
copy's hash check (p1), and vectors_only likely drops image files from search
in a fresh schema (p2, a spike question). Two risks do not call for a split.

## Checked

- Risk 1 (key-for-key copy plus vectors_only with a USER token):
  spike:ov-carry-over/1 answers it for .md files. Failed 0, no VLM calls, same
  uri/level rows, find returns each title.
- Risk 2 (merge): spike:ov-carry-over/3 answers it (spike 2 failed only on its
  own checks, as its README says). Per-directory semantic_and_vectors
  recursive=false costs at most 33 VLM calls per directory, merged overviews
  name both halves, and vectors_only indexes the blogs/ URIs with nothing
  mentioning blog-scraper.
- Sidecar URI rewrite: spike 3 cleared the blog-scraper-only directory by
  regenerating it, not by rewriting text, so the rewrite has no direct
  evidence. It does not need a spike for indexing: in
  `openviking/service/reindex_executor.py` a row's URI comes from the object
  path, and the sidecar text is read only as the directory's embedding and
  abstract text, so a missed occurrence leaves stale text in a summary, not a
  broken index. Its real cost is p1.
- Repo claims: restore-s3.hcl, test_restore_s3.py, ov_identity_probe.py, the
  CLI how-to and the storage.tf identity pattern exist as named. The old-bucket
  listing matches the tree counts (280, 2417, 166, 449).

## Findings

- p1: the rewrite of blog-scraper sidecars changes their hashes, so
  `rclone check --one-way` (which skips only the 26 shared keys) fails and the
  job cannot exit 0 as the outcome promises.
- p2: images (71 files, 41 of them in clips) get no L2 vector under
  vectors_only in a fresh schema, counted unsupported rather than failed.
  Spike question: after a key-for-key copy of a directory holding a .png with
  sidecars in the real overview format, does vectors_only write an L2 row for
  the image and does find return it?

## Notes

The plan's outcome does not check that no sidecar under blogs/ names
blog-scraper. Spike 3 did, and that check would show whether the sed pattern
caught every form the real VLM wrote.
