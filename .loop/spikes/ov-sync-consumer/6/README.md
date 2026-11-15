---
type: spike
title: Spike ov-sync-consumer/6
description: on OpenViking v0.4.17.1-9 (auth_mode oidc), after a lab/jasper USER token deletes a file, does DELETE /api/v1/fs recursive=true remove its emptied folder for good, and does content/batch-write create missing folders under an existing root_uri?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:56:20+00:00'
slug: ov-sync-consumer
n: 6
outcome_written: false
---

# Spike ov-sync-consumer/6

on OpenViking v0.4.17.1-9 (auth_mode oidc), after a lab/jasper USER token deletes a file, does DELETE /api/v1/fs recursive=true remove its emptied folder for good, and does content/batch-write create missing folders under an existing root_uri?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike2.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer 6`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike2.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike2.sh`, which the command used
- `files/drive2.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/drive2.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/mkconf.py`, which the command used
