---
type: spike
title: Spike ov-sync-consumer/7
description: on OpenViking v0.4.17.1-9 (auth_mode oidc) can a lab/jasper USER token create a file under missing folders with content/write, delete it, then delete its emptied folder (DELETE /api/v1/fs recursive=true) so ls no longer lists it, and write the same path again?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:57:56+00:00'
slug: ov-sync-consumer
n: 7
outcome_written: false
---

# Spike ov-sync-consumer/7

on OpenViking v0.4.17.1-9 (auth_mode oidc) can a lab/jasper USER token create a file under missing folders with content/write, delete it, then delete its emptied folder (DELETE /api/v1/fs recursive=true) so ls no longer lists it, and write the same path again?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike3.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer 7`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike3.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike3.sh`, which the command used
- `files/drive3.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/drive3.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/mkconf.py`, which the command used
