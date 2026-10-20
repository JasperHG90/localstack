---
type: spike
title: Spike ov-fresh-instance/1
description: does OpenViking (ov-postgres adapter and ov-ext reflection deltas) on a second schema openviking_v2 in the same Postgres database leave the existing openviking schema and public untouched, and create the new schema itself?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:02:34+00:00'
slug: ov-fresh-instance
n: 1
outcome_written: true
---

# Spike ov-fresh-instance/1

does OpenViking (ov-postgres adapter and ov-ext reflection deltas) on a second schema openviking_v2 in the same Postgres database leave the existing openviking schema and public untouched, and create the new schema itself?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovschema/spike.sh
```

## Outcome

Locally, image v0.4.17.1-9 on pgvector pg17 with a non-superuser `openviking` role that owns the database, as in prod. Phase 1 wrote schema `openviking` (4 tables, 22 ov_context rows, 2 deltas). Then three things ran on schema `openviking_v2` with a new bucket and volume: a boot with 3 writes, a search and a sweep, then 2 deltas recorded, then a restart whose sweep read them (`batches=1`, 2 of 2 rows in `openviking_v2.ov_memory_deltas` marked reflected).
The ov-postgres adapter created `openviking_v2` and its 4 tables. Schema `openviking` stayed the same: insert, update, delete, seq_scan and idx_scan counters matched, and the `pg_dump --schema=openviking` hash was df174f549298e3d4 before and after (632 lines, random `\restrict` token stripped). No new object appeared in `public`; the only new schema was `openviking_v2`. This rules out unqualified names, a hard-coded schema and a shared `public` table on these paths. It settles risk 2: one database with two schemas is safe for the old store.
Side finding the plan must handle: ov-ext opens its delta store in `install()`, before the adapter creates the schema. Its `CREATE TABLE` fails with `schema "openviking_v2" does not exist`, so on the first boot reflection falls back to whole memories and change capture is off. One restart fixes it, and so does creating the schema before the first boot. The script's "opened after restart: 0" count is a grep miss: that INFO line is never logged. The reflected rows show the store opened.
Limits: a stub embedder, reranker and LLM (the sweep proposed nothing), dev auth, deltas recorded through `PgDeltaStore` directly rather than through a real memory extraction, and one local run.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovschema/spike.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovschema/drive.py`, which the command used
- `files/stub.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovschema/stub.py`, which the command used
- `files/ov.conf.tmpl`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovschema/ov.conf.tmpl`, which the command used
