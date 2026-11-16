---
type: spike
title: Spike ov-sync-consumer-binary-upload/3
description: on OpenViking v0.4.17.1-9 (auth_mode oidc) can a PNG reach an exact file URI beside siblings by add into a hidden temp folder, POST /api/v1/fs/mv onto the target, then recursive DELETE of the temp folder, and does mv overwrite in place without a gap and keep the file indexed?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:52:04+00:00'
slug: ov-sync-consumer-binary-upload
n: 3
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/3

on OpenViking v0.4.17.1-9 (auth_mode oidc) can a PNG reach an exact file URI beside siblings by add into a hidden temp folder, POST /api/v1/fs/mv onto the target, then recursive DELETE of the temp folder, and does mv overwrite in place without a gap and keep the file indexed?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike6.sh
```

## Outcome

Exit 0 on local OpenViking v0.4.17.1-9 (same harness as spikes 1 and 2: oidc, SeaweedFS, pgvector, stub models). The move route puts a binary at an exact file URI beside siblings.

Steps per file: `POST /api/v1/resources/temp_upload` (multipart `file`) gives `temp_file_id`; `POST /api/v1/resources {temp_file_id, to: D/.ovsync-upload-<random>, source_name: "diagram.png", wait: true}` stores it in that temp folder (0.7 to 0.9 s); `POST /api/v1/fs/mv {from: D/.ovsync-upload-<random>/diagram.png, to: D/diagram.png}` returned 200 in 0.09 s; the temp folder then held only `.abstract.md` and `.overview.md`, and `DELETE /api/v1/fs?uri=<temp>&recursive=true` removed it (estimated_deleted_count 2).

Round 1: `D/diagram.png` downloaded with the source sha256 (108281 B), `notes.md` (written by content/write) survived, the temp folder was gone from ls, and `find` under D returned the moved file. Round 2, a different PNG onto the same URI: mv over the existing file worked with no delete first. A poller made 111 downloads through the swap and saw only the old bytes, then the new ones, never a missing file.

The image description (VLM) ran once per upload, inside the temp folder; the move did not trigger another. That description sat in the temp folder's summaries, which the cleanup deletes, so the folder D's own summaries are what describe the image afterwards. Limits: local, stub models, oidc only; the run was stopped by the session after its last check, so its run.json exit is from the recorded command. This settles risk 1: binaries can reach their exact URI.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike6.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike6.sh`, which the command used
- `files/drive6.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive6.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
