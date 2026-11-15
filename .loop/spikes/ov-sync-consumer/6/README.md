---
type: spike
title: Spike ov-sync-consumer/6
description: on OpenViking v0.4.17.1-9 (auth_mode oidc), after a lab/jasper USER token deletes a file, does DELETE /api/v1/fs recursive=true remove its emptied folder for good, and does content/batch-write create missing folders under an existing root_uri?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:56:45+00:00'
slug: ov-sync-consumer
n: 6
outcome_written: true
---

# Spike ov-sync-consumer/6

on OpenViking v0.4.17.1-9 (auth_mode oidc), after a lab/jasper USER token deletes a file, does DELETE /api/v1/fs recursive=true remove its emptied folder for good, and does content/batch-write create missing folders under an existing root_uri?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike2.sh
```

## Outcome

Same local setup as spike:ov-sync-consumer/3. `content/batch-write` with `root_uri` set to the existing `viking://user/jasper/resources` returned 400 "batch-write root must be inside a resource directory".
After content/write, then DELETE of the file (wait=true), then `DELETE /api/v1/fs?uri=.../docs/a&recursive=true&wait=true` (200, 2 deleted), `ls` of `docs/` showed only its own `.abstract.md` and `.overview.md` at 0, 5 and 20 s, so `a/` stayed gone from OpenViking's listing. `fs/stat` on `a/` still returned 200 with count 0 the whole time. It also returned 200 for a removed top folder `t/`, which ls no longer listed. Run 3's tree dump shows SeaweedFS keeps empty filer directories, which is what stat sees. The exit 1 comes from this run asserting on stat, which is the wrong test.
Not settled by this run. Run 7 re-checks on ls. Limits: one local run, stub models.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike2.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/spike2.sh`, which the command used
- `files/drive2.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/drive2.py`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/fake.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc1/mkconf.py`, which the command used
