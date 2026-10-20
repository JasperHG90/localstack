---
type: spike
title: Spike ov-save-skill/11
description: 'on OpenViking v0.4.17.1, does POST /api/v1/resources with parent= a missing nested folder fail without create_parent and succeed with create_parent: true (and does to= create missing folders)?'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T15:20:39+00:00'
slug: ov-save-skill
n: 11
outcome_written: true
---

# Spike ov-save-skill/11

on OpenViking v0.4.17.1, does POST /api/v1/resources with parent= a missing nested folder fail without create_parent and succeed with create_parent: true (and does to= create missing folders)?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovparent/spike.sh
```

## Outcome

Ran locally on image v0.4.17.1-9 (SeaweedFS, pgvector, local OIDC, stub models) as lab/jasper with a USER token. Each save was a text file sent the way plugin 2.1.1 does it: temp_upload first, then POST /api/v1/resources with source_name and temp_file_id.
With parent= set to a missing nested folder and no create_parent, the save fails at once with HTTP 404 "Resource not found", even with wait=false. The server log says "Parent URI does not exist". Adding `create_parent: true` (a JSON boolean with that exact name) returns 200 and creates both newroot1/ and newroot1/sub/. The file lands at newroot1/sub/bravo/bravo.md, because each resource gets its own folder named after the file stem, and find returns it. Saving again into the now-existing folder with create_parent: true also returns 200, keeps the earlier entries, and both files stay findable.
With `to=` set to a full URI under missing folders, the save succeeds with or without create_parent and creates the parents. But to= names the resource's own folder, so to=.../sub/delta.md produced sub/delta.md/delta.md. No other field is needed besides path or temp_file_id. The model rejects unknown fields: parent_auto_create got HTTP 400 "Extra inputs are not permitted".
This settles p1. Having the wrapper send `create_parent: true` with parent= fixes saves into new folders and does no harm when the folder already exists.
Limits: one local run on the uploaded-file path only, so the remote-URL `path=` path was not tried. The embeddings were stubs, so the find hits show the file was indexed but say nothing about ranking.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovparent/spike.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovparent/drive.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovparent/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovparent/mkconf.py`, which the command used
