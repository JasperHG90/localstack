---
type: spike
title: Spike ov-sync-consumer-binary-upload/2
description: on OpenViking v0.4.17.1-9 (auth_mode oidc) does resources/temp_upload plus POST /api/v1/resources with parent=folder and source_name store a PNG at an exact file URI byte for byte, overwrite it in place, keep siblings, and return only once stored with wait=true?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T09:44:19+00:00'
slug: ov-sync-consumer-binary-upload
n: 2
outcome_written: true
---

# Spike ov-sync-consumer-binary-upload/2

on OpenViking v0.4.17.1-9 (auth_mode oidc) does resources/temp_upload plus POST /api/v1/resources with parent=folder and source_name store a PNG at an exact file URI byte for byte, overwrite it in place, keep siblings, and return only once stored with wait=true?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike5.sh
```

## Outcome

Same harness, with `parent` in place of `to` (`POST /api/v1/resources {temp_file_id, parent:D, source_name:"diagram.png", wait:true}`). It keeps siblings (notes.md and earlier uploads stayed), but it wraps every upload in a new folder named after the stem: the PNG landed at `D/diagram/diagram.png` (108281 B, `root_uri` `.../ref/diagram`) and `D/diagram.png` answered 404. A second add with the same name made `D/diagram_1/diagram.png` rather than overwriting. `create_parent:true` on a missing parent made the same wrapper (`newdir/sub/diagram/diagram.png`). The add still returned 200 while the fake VLM answered 500 to image calls.
With spike:ov-sync-consumer-binary-upload/1 this shows that on v0.4.17.1-9 no add_resource shape stores a binary at an exact file URI beside other files and overwrites it there. `to=D` replaces all of D. `to=D/name` stores `D/name/name`. `parent=D` stores `D/<stem>/name` and never overwrites.
Risk 1 is real. Not tried: moving the stored file into place with `fs/mv`, and a dedicated folder per binary (`to=D/name`, overwritten by a re-add).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike5.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/spike5.sh`, which the command used
- `files/drive5.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/drive5.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-upload/mkconf.py`, which the command used
