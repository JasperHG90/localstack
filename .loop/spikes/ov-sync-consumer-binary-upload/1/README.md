---
type: spike
title: Spike ov-sync-consumer-binary-upload/1
description: on OpenViking v0.4.17.1-9 (auth_mode oidc) does resources/temp_upload plus POST /api/v1/resources (to=folder, source_name) store a PNG at an exact file URI byte for byte, overwrite it in place, keep siblings, and return only once stored with wait=true?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:43:12+00:00'
slug: ov-sync-consumer-binary-upload
n: 1
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/1

on OpenViking v0.4.17.1-9 (auth_mode oidc) does resources/temp_upload plus POST /api/v1/resources (to=folder, source_name) store a PNG at an exact file URI byte for byte, overwrite it in place, keep siblings, and return only once stored with wait=true?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike4.sh
```

## Outcome

Local v0.4.17.1-9 (oidc, SeaweedFS 4.48, stub models), lab/jasper token. `POST /api/v1/resources/temp_upload` takes multipart field `file` and answers `{"result":{"temp_file_id":"upload_<hex>.png"}}`. `POST /api/v1/resources {temp_file_id, to, source_name, wait:true}` returns 200 in under 1 s with queues drained, and `GET /api/v1/content/download` (raw bytes) then gave back the 108281 B PNG with the same sha256.
But `to` is the resource root folder, not the file. `to=D/diagram.png` stored `D/diagram.png/diagram.png` (download of `D/diagram.png` answers 400). `to=D, source_name=name` stores `D/name`, but it replaces all of D: notes.md (from content/write) went at the first add, and each later add (other.png, then diagram.png again) left only itself. Overwrite therefore "works" only by wiping siblings.
wait=false returns at once with a task_id: 404 right away, exact after 5 s. With the fake VLM answering 500 to every image call, the add still returned 200 and stored the exact bytes (the summary is logged as failed).
Does not settle risk 1: the `to` shape cannot place a binary at an exact file URI beside other files. `parent` was not tried in this run.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike4.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike4.sh`, which the command used
- `files/drive4.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive4.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
