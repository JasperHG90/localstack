---
type: spike
title: Spike ov-sync-consumer-binary-upload/8
description: 'on OpenViking v0.4.17.1-9 (oidc), after deleting a natively stored PNG (file DELETE then recursive DELETE of D/diagram.png), is ls D/diagram.png empty with the file 404, and does a re-add to the same to=D/diagram.png store the new bytes with no _1 folder? (also: non-recursive DELETE of the live image folder, and isDir in ls D)'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:26:37+00:00'
slug: ov-sync-consumer-binary-upload
n: 8
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/8

on OpenViking v0.4.17.1-9 (oidc), after deleting a natively stored PNG (file DELETE then recursive DELETE of D/diagram.png), is ls D/diagram.png empty with the file 404, and does a re-add to the same to=D/diagram.png store the new bytes with no _1 folder? (also: non-recursive DELETE of the live image folder, and isDir in ls D)

The command exited 0:

```
timeout 600 /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike10.sh
```

## Outcome

Exit 0 on local OpenViking v0.4.17.1-9 (oidc, SeaweedFS, pgvector, stub models). Both checks in the plan hold. (1) After DELETE of D/diagram.png/diagram.png (200, estimated_deleted_count 1) and recursive DELETE of D/diagram.png with wait=true (200, count 2), `ls D/diagram.png` with the consumer's parameters returns 200 `[]` (not even `.abstract.md` or `.overview.md` are left) and content/download of the file returns 404 NOT_FOUND. (2) A second add with `to=D/diagram.png` on that ghost folder stores b.png byte for byte (415781 B, sha256 ba47cb7b...4f8ad1) at D/diagram.png/diagram.png. `ls D/diagram.png` then lists `.abstract.md`, `.overview.md` and `diagram.png`, and no `_1` entry appears in D or inside the folder.
Fact 3: a non-recursive `DELETE /api/v1/fs?uri=D/diagram.png&wait=true` on a folder holding the live image returns 412 FAILED_PRECONDITION, "Cannot remove directory without --recursive" with details.expected_flag "recursive". The image survives with an identical sha256.
Fact 4: `ls D` reports D/diagram.png as isDir=True, size 0, in all three states (live image, ghost empty folder, live after re-add). A plain.png written by content/write reports isDir=False, size 17. So isDir in `ls D` cannot tell a live image folder from a ghost one. Only `ls D/name` can.
Settles risk 1. Limits: one run, one PNG pair, stub models, oidc only. The re-add ran right after the delete, with no wait.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike10.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike10.sh`, which the command used
- `files/drive10.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive10.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
