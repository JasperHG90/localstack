---
type: spike
title: Spike ov-carry-over/3
description: can blog-scraper be merged into blogs by a storage copy plus a non-recursive semantic reindex of only the merged directories, with VLM calls bounded per directory, and does vectors_only then index every file at its blogs/ URI?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:45:05+00:00'
slug: ov-carry-over
n: 3
outcome_written: true
---

# Spike ov-carry-over/3

can blog-scraper be merged into blogs by a storage copy plus a non-recursive semantic reindex of only the merged directories, with VLM calls bounded per directory, and does vectors_only then index every file at its blogs/ URI?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmerge/spike.sh
```

## Outcome

Ran locally on v0.4.17.1-9 (SeaweedFS 4.48, pgvector, local OIDC, stub VLM). A wrote blogs/{src 2, notes 1} and blog-scraper/{src 2, notes 40, extra 1}. Into fresh B's bucket went blogs keys as-is, then blog-scraper keys remapped to blogs/ with ignore-existing.
`POST /content/reindex mode=semantic_and_vectors recursive=false`, run children first and then on blogs/, rewrote only that directory's sidecars. VLM calls: blogs/src 4+1, blogs/notes 32+1 (41 files, capped by `overview_sample_limit` 32, freshness 32 of 41 sampled), blogs/ 0+1, so 41 in all. The cost is at most 33 per directory, never the whole subtree. The new blogs/src and blogs/ overviews name all 4 src files.
A blog-scraper-only directory (extra/) keeps copied sidecars that name `blog-scraper` (2 keys), so it needs the same per-directory call (1+1 VLM). After that, no key under blogs/ names blog-scraper.
`vectors_only` on blogs then gave failed 0 and 0 VLM calls. It rebuilt 54 records, exactly the expected blogs/ uri|level set (4 dirs L0+L1, 46 files L2), and no row text mentions blog-scraper. Find on 8 titles returned each file at its blogs/ URI. This settles risk 2.
Limits: stub models, one small run. A directory over 32 files gets a sampled overview. Every directory that came only from blog-scraper also needs the per-directory call. stdout kept only its last 20000 bytes, so A's write lines and the merge-copy counts were cut.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmerge/spike.sh`, which the command used
