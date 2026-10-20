---
type: spike
title: Spike ov-fresh-instance/3
description: under auth_mode oidc on an empty bucket, does a lab/jasper token pass ls, mkdir, write, read, find and search while the bucket gets no _system/ files and nothing outside lab/ but the preset default tree?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:28:46+00:00'
slug: ov-fresh-instance
n: 3
outcome_written: true
---

# Spike ov-fresh-instance/3

under auth_mode oidc on an empty bucket, does a lab/jasper token pass ls, mkdir, write, read, find and search while the bucket gets no _system/ files and nothing outside lab/ but the preset default tree?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/spike3.sh
```

## Outcome

Same local setup as spike:ov-fresh-instance/2 (image v0.4.17.1-9, auth_mode oidc, empty SeaweedFS 4.48 bucket, schema `openviking_v2` created before boot); only the final assertion changed. A token with ov_account=lab, ov_user=jasper passed all 9 calls on the first try (health, ls viking:// and viking://resources, mkdir, write, read, find, search, recursive ls) with no Admin API call.
The bucket held 31 keys afterwards: 6 under `lab/resources/` (the written note and its directory files), and 25 outside `lab/`, every one matching the exact preset allowlist: `backend_meta.json` plus directory markers, `.abstract.md` and `.overview.md` for `default/resources` and `default/user/default/{memories,peers,privacy,resources,sessions,skills}`. No `_system/` key, no other account prefix, no user besides `default` under `default/`.
This settles risk 1 as the plan now words it. Limits: one local run, stub embedder, reranker and LLM, a plain-http fake issuer in place of Vault, the admin S3 key; preset files were checked by path, not by content.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike3.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/spike3.sh`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/fake.py`, which the command used
- `files/probe.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/probe.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/mkconf.py`, which the command used
- `files/keys.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/keys.py`, which the command used
