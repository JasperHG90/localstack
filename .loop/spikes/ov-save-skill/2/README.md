---
type: spike
title: Spike ov-save-skill/2
description: can a lab/jasper USER token create, replace and append viking://user/jasper/resources/.map.md and read it back exactly (content/read and the plugin viking_read path), and what does each write cost in VLM calls and search visibility?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:44:09+00:00'
slug: ov-save-skill
n: 2
outcome_written: true
---

# Spike ov-save-skill/2

can a lab/jasper USER token create, replace and append viking://user/jasper/resources/.map.md and read it back exactly (content/read and the plugin viking_read path), and what does each write cost in VLM calls and search visibility?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmap/spike.sh
```

## Outcome

Ran locally on image v0.4.17.1-9 (SeaweedFS 4.48, pgvector, stub OIDC and models) with a lab/jasper USER token, over a seeded tree of 3 subdirectories and 6 files. POST content/write on viking://user/jasper/resources/.map.md returned HTTP 200 for create, replace and append. After each write, GET content/read and the Hermes plugin's viking_read path (level=full calls content/read; the default level=overview stats the URI, sees a file and also calls content/read) returned the exact text, append included. The dotfile name was not refused, so `_map.md` was not needed.
With the default processing mode, each write made 1 VLM call and rewrote only the resources root's .abstract.md and .overview.md. No subdirectory summary changed, so a write does not summarize the whole tree. In that mode the map got 0 vector rows and did not appear in find or search. It is hidden from ls and listed only with show_all_hidden.
A replace with processing_mode=vectors_only made 0 VLM calls and changed only the map key, but it added 1 vector row, and find and search then returned the map at the top for its text.
This settles risk 2. Limits: one local run on a 14-key tree with stub models. The real root has more children, so the one root overview call costs more there, but it stays one call.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmap/spike.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmap/drive.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmap/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovmap/mkconf.py`, which the command used
