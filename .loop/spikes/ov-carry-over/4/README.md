---
type: spike
title: Spike ov-carry-over/4
description: after a key-for-key carry-over into a fresh OpenViking v0.4.17.1-9 schema, does an image file (png, real "### [name](uri)" overview format) get an L2 vector from vectors_only or any reindex mode, and if not, what bounded step makes find return it?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T15:13:14+00:00'
slug: ov-carry-over
n: 4
outcome_written: true
---

# Spike ov-carry-over/4

after a key-for-key carry-over into a fresh OpenViking v0.4.17.1-9 schema, does an image file (png, real "### [name](uri)" overview format) get an L2 vector from vectors_only or any reindex mode, and if not, what bounded step makes find return it?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg/spike.sh
```

## Outcome

Real overviews read from the old bucket (5 image folders, GET only) give each entry as `### [name](viking://...)`, while 0.4.17.1's `ReindexExecutor._parse_overview_md` matches only `## name`. So in a fresh schema an image has no vector source. Images sit in 36 folders: clips 41 files in 6 folders, blog-scraper 30 files in 30 one-image folders, blogs and leo none.
Locally (v0.4.17.1-9, stub VLM writing that format), A ingested 2 pngs via temp_upload plus add_resource, and find returned each. After a key-for-key copy into fresh B, `vectors_only` on clips gave rebuilt 7, unsupported 2 (both pngs), failed 0, and no png L2 row. Find returned only the folder whose overview names the image.
No reindex mode fixes this. `semantic_and_vectors` recursive=false (1 image, 1 file and 1 overview VLM call), recursive=true (the same) and on the png URI itself all left the png with 0 L2 rows, because the semantic pass runs with skip_vectorization and the vector pass reuses the broken parser. A second add_resource of the same png to the same folder made no image call and wrote no row.
What works: copying the png's old L2 row into B's table with SQL (INSERT ... SELECT, 0 VLM calls). It survived a later `vectors_only` and find returned the png itself, although `vectors_only` still counted it unsupported.
This settles p2: the risk is real for all 71 images, and copying their 71 old L2 rows from the old schema, read only, is the bounded fix. Limits: stub models, 2 pngs, and the real old schema was not checked for the 71 image rows or for embeddings the new instance can use.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg/spike.sh`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg/fake.py`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg/drive.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg/mkconf.py`, which the command used
- `files/s3tool.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovimg/s3tool.py`, which the command used
