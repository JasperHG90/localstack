---
type: spike
title: Spike ov-sync-consumer-binary-upload/8
description: 'on OpenViking v0.4.17.1-9 (oidc), after deleting a natively stored PNG (file DELETE then recursive DELETE of D/diagram.png), is ls D/diagram.png empty with the file 404, and does a re-add to the same to=D/diagram.png store the new bytes with no _1 folder? (also: non-recursive DELETE of the live image folder, and isDir in ls D)'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:26:26+00:00'
slug: ov-sync-consumer-binary-upload
n: 8
outcome_written: false
---

# Spike ov-sync-consumer-binary-upload/8

on OpenViking v0.4.17.1-9 (oidc), after deleting a natively stored PNG (file DELETE then recursive DELETE of D/diagram.png), is ls D/diagram.png empty with the file 404, and does a re-add to the same to=D/diagram.png store the new bytes with no _1 folder? (also: non-recursive DELETE of the live image folder, and isDir in ls D)

The command exited 0:

```
timeout 600 /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike10.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer-binary-upload 8`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike10.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike10.sh`, which the command used
- `files/drive10.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive10.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
