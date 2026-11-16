---
type: spike
title: Spike ov-sync-consumer-binary-upload/4
description: on OpenViking v0.4.17.1-9 (oidc) does the add-to-temp-folder, fs/mv, rm route put a PNG at D/diagram.png when D and its parents do not exist yet, and does reusing one fixed temp folder name (also when left over holding its summaries) still work and overwrite?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:15:29+00:00'
slug: ov-sync-consumer-binary-upload
n: 4
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/4

on OpenViking v0.4.17.1-9 (oidc) does the add-to-temp-folder, fs/mv, rm route put a PNG at D/diagram.png when D and its parents do not exist yet, and does reusing one fixed temp folder name (also when left over holding its summaries) still work and overwrite?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike7.sh
```

## Outcome

Exit 1 on local OpenViking v0.4.17.1-9 (spike 3's harness). On a fresh tree, `POST /api/v1/resources {temp_file_id, to: <missing D>/.ovsync-upload-diagram.png, source_name, wait: true}` succeeded without `create_parent` and created D and its missing parents. The mv then put the exact bytes at D/diagram.png (sha256 matched for a.png, then b.png and c.png over the same URI, reusing one fixed temp folder name, including adding into a leftover temp folder). The exit is 1 because the temp folder was still listed in D after its recursive delete in all three checks, so the move route leaves hidden folders behind. The session stopped the spike after this run; the operator then chose OpenViking's native layout (`to = D/<name>`, stored as `D/<name>/<name>`), which needs no temp folder or move. What carries over: add resource creates missing parents.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike7.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike7.sh`, which the command used
- `files/drive7.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive7.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
