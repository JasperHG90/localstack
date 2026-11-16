---
type: spike
title: Spike ov-sync-consumer-binary-upload/6
description: on OpenViking v0.4.17.1-9 (oidc) after add to=D/diagram.png (stored D/diagram.png/diagram.png), does DELETE of the file then DELETE D/diagram.png recursive (or the recursive DELETE alone) remove D/diagram.png from ls D at once, after 5 s, after 30 s, or never?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:22:01+00:00'
slug: ov-sync-consumer-binary-upload
n: 6
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/6

on OpenViking v0.4.17.1-9 (oidc) after add to=D/diagram.png (stored D/diagram.png/diagram.png), does DELETE of the file then DELETE D/diagram.png recursive (or the recursive DELETE alone) remove D/diagram.png from ls D at once, after 5 s, after 30 s, or never?

The command exited 1:

```
timeout 560 /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike9.sh
```

## Outcome

Exit 1 on local OpenViking v0.4.17.1-9 (spike 3's harness: oidc, SeaweedFS, pgvector, stub models). Deleting a natively stored PNG leaves `D/diagram.png` listed in `ls D` for good, as a `dir` entry, in all three cases: A (D held notes.md; file DELETE then recursive DELETE of D/diagram.png), B (D did not exist before the add; same two DELETEs) and C (recursive DELETE of D/diagram.png alone).
Every DELETE returned 200: the file DELETE with estimated_deleted_count 1, the follow-up recursive DELETE with 2, and in case C the single recursive DELETE with 3. `ls D` with the consumer's parameters (show_all_hidden=true, node_limit=1000, offset=0), with and without output=original, still showed `diagram.png` (dir) right away, after 5 s and after 30 s.
The leftover is an empty directory, not content: stat and content/download of `D/diagram.png/diagram.png` return 404, `ls D/diagram.png` returns `[]`, `fs/stat D/diagram.png` returns 200 isDir size 0, and SeaweedFS's `fs.tree` shows `diagram.png` as a leaf with no children under each D. This matches what spike:ov-sync-consumer/6 saw for fs/stat.
So a consumer that lists D after a delete sees a ghost folder for each deleted image and has to treat an empty `<name>` dir as absent. Limits: local, stub models, oidc only, one PNG, waited up to 30 s.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike9.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike9.sh`, which the command used
- `files/drive9.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive9.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
