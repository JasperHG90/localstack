---
type: spike
title: Spike ov-fresh-instance/2
description: does OpenViking v0.4.17.1-9 under auth_mode oidc, on an empty bucket and empty schema, serve ls, write and search for a token with ov_account=lab ov_user=jasper, and does it create any account or user besides lab/jasper?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:07:33+00:00'
slug: ov-fresh-instance
n: 2
outcome_written: true
---

# Spike ov-fresh-instance/2

does OpenViking v0.4.17.1-9 under auth_mode oidc, on an empty bucket and empty schema, serve ls, write and search for a token with ov_account=lab ov_user=jasper, and does it create any account or user besides lab/jasper?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/spike.sh
```

## Outcome

Ran locally: image v0.4.17.1-9 started with `python -m ov_ext --with-bot` and auth_mode oidc, against an empty SeaweedFS 4.48 bucket `openviking-v2`, a pre-created empty schema `openviking_v2`, and a local issuer that serves discovery and JWKS. A token with literal claims ov_account=lab and ov_user=jasper passed all 9 calls on the first try, with no bootstrap: /health (resolved lab/jasper, role user), ls viking:// and viking://resources (empty), mkdir, write (semantic and vector status `complete`), read, find, and search (2 hits). ls viking://user/jasper/memories also returned 200. So OIDC needs no Admin API call and no api_key boot, and phase B (the root-key fallback) never ran.
The bucket never holds an object under `_system/`. Under OIDC no APIKeyManager is built, so no accounts.json or users.json is written. Lab's tree is created lazily by writes (6 keys under `lab/resources/`, none under `lab/user/`).
The risk is still real on its other half. Before the first request, the boot writes account `default` and user `default`: 24 keys under `default/resources/` and `default/user/default/{memories,peers,privacy,resources,sessions,skills}/`, plus `backend_meta.json`. The writer is `OpenVikingService` init (openviking/service/core.py:367-369), which calls initialize_account_directories and initialize_user_directories for the service's default user every time it starts. The plan's "only lab/jasper" outcome cannot hold as written, so it should allow the `default` preset tree.
Limits: one local run, stub embedder, reranker and LLM, the issuer at plain http://fake:8000 in place of Vault, the admin S3 key, and the schema created before boot (spike:ov-fresh-instance/1 explains why).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/spike.sh`, which the command used
- `files/fake.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/fake.py`, which the command used
- `files/probe.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/probe.py`, which the command used
- `files/mkconf.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/mkconf.py`, which the command used
- `files/keys.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovboot/keys.py`, which the command used
