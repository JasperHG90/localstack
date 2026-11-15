---
type: spike
title: Spike ov-sync-consumer/3
description: on OpenViking v0.4.17.1-9 (auth_mode oidc) can a lab/jasper USER token create a file under missing parent folders with content/write or content/batch-write, then delete the file and its emptied folder via DELETE /api/v1/fs, and with which parameters?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:55:12+00:00'
slug: ov-sync-consumer
n: 3
outcome_written: true
---

# Spike ov-sync-consumer/3

on OpenViking v0.4.17.1-9 (auth_mode oidc) can a lab/jasper USER token create a file under missing parent folders with content/write or content/batch-write, then delete the file and its emptied folder via DELETE /api/v1/fs, and with which parameters?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike.sh
```

## Outcome

Local OpenViking v0.4.17.1-9 under auth_mode oidc (SeaweedFS 4.48, pgvector, local issuer, stub models), lab/jasper USER token. `POST /api/v1/content/write` (default mode, wait=true) at `resources/projects/w/docs/a/b.md` returned 200 and created all four missing folders (it reported mode "create"). Read-back was exact.
`POST /api/v1/content/batch-write` with `root_uri` set to a missing folder returned 404 "File not found" for the root_uri, so it does not create its root.
`DELETE /api/v1/fs?uri=<file>&wait=true` returned 200 and stat then gave 404. The emptied folder still held the `.abstract.md` and `.overview.md` OpenViking writes, so a non-recursive delete returned 412 "Cannot remove directory without --recursive". `recursive=true` returned 200, but stat still found `a/` right afterwards with 2 children. A recursive delete of `docs/` then cleared it from ls.
Exit 1, not settled. Run 4 checks whether the folder comes back. Limits: one local run, stub models.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/drive.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/mkconf.py`, which the command used
