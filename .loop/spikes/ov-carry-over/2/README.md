---
type: spike
title: Spike ov-carry-over/2
description: can blog-scraper be merged into blogs by a storage copy plus a non-recursive semantic reindex of only the merged directories, with VLM calls bounded per directory, and does vectors_only then index every file at its blogs/ URI?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:45:06+00:00'
slug: ov-carry-over
n: 2
outcome_written: true
---

# Spike ov-carry-over/2

can blog-scraper be merged into blogs by a storage copy plus a non-recursive semantic reindex of only the merged directories, with VLM calls bounded per directory, and does vectors_only then index every file at its blogs/ URI?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmerge/spike.sh
```

## Outcome

Same setup as run 3. Every regeneration and indexing check passed, with VLM calls of 4+1, 32+1, 0+1 and 1+1. The run exited 1 on two faults in the check itself, not in OpenViking.
The row diff compared Python sort order with Postgres collation: both held the same 54 rows. Find missed the 4 blogs/src files because the stub rerank scored every document 0.5, so the top 5 of 54 was arbitrary. A debug run showed that all 4 come back with limit 60 or with target_uri blogs/src.
Run 3 fixed both (C-locale sort, cosine rerank stub) and is the one to cite.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmerge/spike.sh`, which the command used
