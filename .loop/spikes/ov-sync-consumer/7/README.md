---
type: spike
title: Spike ov-sync-consumer/7
description: on OpenViking v0.4.17.1-9 (auth_mode oidc) can a lab/jasper USER token create a file under missing folders with content/write, delete it, then delete its emptied folder (DELETE /api/v1/fs recursive=true) so ls no longer lists it, and write the same path again?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:58:10+00:00'
slug: ov-sync-consumer
n: 7
outcome_written: true
---

# Spike ov-sync-consumer/7

on OpenViking v0.4.17.1-9 (auth_mode oidc) can a lab/jasper USER token create a file under missing folders with content/write, delete it, then delete its emptied folder (DELETE /api/v1/fs recursive=true) so ls no longer lists it, and write the same path again?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike3.sh
```

## Outcome

Local OpenViking v0.4.17.1-9 under auth_mode oidc (SeaweedFS 4.48, pgvector, local issuer, stub models), lab/jasper USER token, fresh tree with no `resources/projects/`. `POST /api/v1/content/write` `{uri, content, wait: true}` at `projects/x/docs/a/b.md` returned 200, created every missing parent and read back exactly. `DELETE /api/v1/fs?uri=<file>&wait=true` returned 200 and the read then failed.
The emptied folder still holds the `.abstract.md` and `.overview.md` OpenViking writes, so `DELETE /api/v1/fs?uri=<folder>&wait=true` returns 412. Adding `recursive=true` returns 200 (2 deleted). ls of the parent then omitted the folder at 0, 5 and 20 s. A second content/write to the same path returned 200 and read back. Judge deletes by ls or read: fs/stat keeps returning 200 on the removed folder, an empty SeaweedFS directory (spike:ov-sync-consumer/6).
Use content/write rather than `content/batch-write`. Batch-write returned 404 for an operation under missing subfolders even with an existing folder as root_uri (default mode replace, create/upsert not tried). It also refuses a missing root (spike:ov-sync-consumer/3) and the resources root (spike:ov-sync-consumer/6).
This settles risk 1. Limits: one local run with stub models. The write and rm handlers check no role beyond the request identity, so another auth mode should not change the answer, but only oidc was run.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike3.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike3.sh`, which the command used
- `files/drive3.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/drive3.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/mkconf.py`, which the command used
