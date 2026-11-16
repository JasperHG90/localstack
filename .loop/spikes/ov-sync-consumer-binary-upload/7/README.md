---
type: spike
title: Spike ov-sync-consumer-binary-upload/7
description: 'on OpenViking v0.4.17.1-9 (oidc), after deleting a natively stored PNG (file DELETE then recursive DELETE of D/diagram.png), is ls D/diagram.png empty with the file 404, and does a re-add to the same to=D/diagram.png store the new bytes with no _1 folder? (also: non-recursive DELETE of the live image folder, and isDir in ls D)'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:25:58+00:00'
slug: ov-sync-consumer-binary-upload
n: 7
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/7

on OpenViking v0.4.17.1-9 (oidc), after deleting a natively stored PNG (file DELETE then recursive DELETE of D/diagram.png), is ls D/diagram.png empty with the file 404, and does a re-add to the same to=D/diagram.png store the new bytes with no _1 folder? (also: non-recursive DELETE of the live image folder, and isDir in ls D)

The command exited 1:

```
timeout 600 /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike10.sh
```

## Outcome

Exit 1 because of a bug in the driver, not because the risk is real: the "only diagram.png inside" check counted the `.abstract.md` and `.overview.md` that OpenViking writes into every folder. The data itself matches spike 8, which reran with that check fixed.
Seen here: after the file DELETE and the recursive DELETE, `ls D/diagram.png` returned 200 `[]` and the download returned 404. A re-add of b.png stored its exact sha256 (ba47cb7b...) at D/diagram.png/diagram.png, and no `_1` entry appeared in D or inside D/diagram.png. A non-recursive DELETE of the live folder returned 412 FAILED_PRECONDITION and the image survived. `ls D` reported isDir=True for D/diagram.png in every state and isDir=False for plain.png. Cite spike 8, not this one.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike10.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike10.sh`, which the command used
- `files/drive10.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive10.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
