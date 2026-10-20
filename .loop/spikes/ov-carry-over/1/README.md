---
type: spike
title: Spike ov-carry-over/1
description: does a key-for-key S3 copy of a user/jasper resources tree (dir markers, .abstract.md, .overview.md) into a fresh OpenViking v0.4.17.1-9 bucket and empty schema get fully indexed by POST /content/reindex mode=vectors_only with a USER token, with no VLM call, and searchable by title?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:32:46+00:00'
slug: ov-carry-over
n: 1
outcome_written: true
---

# Spike ov-carry-over/1

does a key-for-key S3 copy of a user/jasper resources tree (dir markers, .abstract.md, .overview.md) into a fresh OpenViking v0.4.17.1-9 bucket and empty schema get fully indexed by POST /content/reindex mode=vectors_only with a USER token, with no VLM call, and searchable by title?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry/spike.sh
```

## Outcome

Ran locally on image v0.4.17.1-9 with SeaweedFS 4.48, pgvector pg17 and OIDC from a local issuer (/health reported lab/jasper, role user). Instance A wrote 5 files under viking://user/jasper/resources/carry, and the VLM produced the sidecars: 17 keys, made of 4 directory markers, 4 .abstract.md, 4 .overview.md and 5 files. The spike copied all 17 keys, and nothing above the tree, into the bucket of a running fresh instance B whose schema was empty and whose bucket had no lab/ keys.
On B, POST /api/v1/content/reindex mode=vectors_only with the USER token returned `completed`, with scanned 9, rebuilt 13 and failed 0, and made 0 chat calls (VLM count stayed at 17, embeddings rose 53 to 66). B's ov_context then held the same 13 uri/level rows for the tree as A: L0 and L1 for each of the 4 directories, plus L2 for each of the 5 files. A find on each of the 5 titles returned that file.
This rules out all three ways the risk could hold. vectors_only does index files that have no vector record, it does not call the VLM, and a USER token may re-index a viking://user/jasper/resources tree. It settles risk 1. The storage-level copy works.
Side finding: SeaweedFS refuses CopyObject on a directory marker key (NoSuchKey), so the spike copied with get and put. The plan's rclone copy is not affected by this.
Limits: one local run on a 17-key tree, not the 2863 real objects. The models were stubs (bag-of-words embeddings, flat rerank), so find at limit 5 over 13 rows is weak evidence of ranking. The source tree was written through /content/write, not through ov-clip or the blog scraper.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry/spike.sh`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry/mkconf.py`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry/drive.py`, which the command used
- `files/copy.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovcarry/copy.py`, which the command used
