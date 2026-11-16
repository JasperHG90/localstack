---
type: spike
title: Spike ov-sync-consumer-binary-upload/6
description: on OpenViking v0.4.17.1-9 (oidc) after add to=D/diagram.png (stored D/diagram.png/diagram.png), does DELETE of the file then DELETE D/diagram.png recursive (or the recursive DELETE alone) remove D/diagram.png from ls D at once, after 5 s, after 30 s, or never?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:21:40+00:00'
slug: ov-sync-consumer-binary-upload
n: 6
outcome_written: false
---

# Spike ov-sync-consumer-binary-upload/6

on OpenViking v0.4.17.1-9 (oidc) after add to=D/diagram.png (stored D/diagram.png/diagram.png), does DELETE of the file then DELETE D/diagram.png recursive (or the recursive DELETE alone) remove D/diagram.png from ls D at once, after 5 s, after 30 s, or never?

The command exited 1:

```
timeout 560 /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike9.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer-binary-upload 6`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike9.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike9.sh`, which the command used
- `files/drive9.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive9.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
