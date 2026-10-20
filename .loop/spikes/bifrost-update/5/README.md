---
type: spike
title: Spike bifrost-update/5
description: after the upgrade, does Bifrost 2.3.1 pass the smoke script, serve a bare-string rerank through the OpenViking key, show traffic in Prometheus, and plan clean?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T10:27:47+00:00'
slug: bifrost-update
n: 5
outcome_written: true
---

# Spike bifrost-update/5

after the upgrade, does Bifrost 2.3.1 pass the smoke script, serve a bare-string rerank through the OpenViking key, show traffic in Prometheus, and plan clean?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bf-verify/verify.sh
```

## Outcome

Yes. On 2026-10-20, before the apply, a forced `backup-postgres` run (periodic-1792491282, alloc 7112e586, both tasks exit 0) wrote `gs://localstack-cluster-backups/postgres/pgdumpall-2026-10-20.sql.gz` (1,399,446,141 bytes, 10:24:51 UTC). It holds the `bifrost` database at 2.0.0, which is the only way back because the 2.1.0-2.3.1 store migrations cannot be undone. At 10:25 UTC the applications root updated `nomad_job.bifrost` to `docker.io/maximhq/bifrost:v2.3.1` and replaced `null_resource.bifrost_ready`. The deployment is successful.

stdout.txt: `scripts/bifrost_smoke.py` against v2.3.1 passes all five checks. Inference auth is enforced, and a bogus key is refused with the renamed `access_not_found`. `/metrics` is behind basic auth, no admin path is open, the four named virtual keys survive, and embeddings reach embark. A bare-string rerank through OpenViking's virtual key returned 200 with the right order. Prometheus counts 21 Bifrost requests in the 10 minutes after the switch. A second applications-root plan reports no changes, so every `bifrost_virtual_key` is untouched.

Not done: the smoke script's docstring asks for a run against the old gateway first, as a baseline. It was not run before this apply, so the before/after comparison exists only through spike 4 (keys created on 2.0.0 survive the migration).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bf-verify/verify.sh`, which the command used
