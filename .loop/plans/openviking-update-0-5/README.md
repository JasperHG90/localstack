---
type: plan
title: 'Plan: openviking-update-0-5'
description: Move OpenViking from v0.4.17.1 to v0.5.6 once ov-postgres and ov-ext ship 0.5.6-compatible tags, and drop the ov-ext rerank settings 0.5.x makes redundant.
tags:
- plan
slug: openviking-update-0-5
epic: null
depends_on: []
priority: null
schema_version: '2.0'
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:52:44+00:00'
---

# openviking-update-0-5

Relayed from: none

## Intent

Move OpenViking from v0.4.17.1 to v0.5.6, on ov-postgres v0.7.0 and ov-ext
v0.8.0. Both were released on 2026-11-27 from one commit (10ffca50,
JasperHG90/openviking_extensions#24, closing #23 and #13 to #19).

OpenViking runs v0.4.17.1: `openviking_base_image` and `openviking_image` in
`deployments/applications/services.tf`, built by
`deployments/applications/services/openviking/Dockerfile.openviking`, which
pins ov-postgres v0.6.0 and ov-ext v0.7.1.

1. Set `openviking_base_image` to ghcr.io/volcengine/openviking:v0.5.6 and
   `openviking_image` to ghcr.io/jasperhg90/openviking:v0.5.6-1. Move both
   git pins in `Dockerfile.openviking` to ov-postgres-v0.7.0 and
   ov-ext-v0.8.0. The v0.5.6 base still ships python 3.13 at `/app/.venv`,
   so the `--target` install path holds. Build, verify and push with the
   justfile beside the Dockerfile (just build, just verify, just push).
2. Remove `OV_RETRIEVAL_RERANK_MAX_CALLS` and `OV_RETRIEVAL_RERANK_FINAL` from
   `deployments/applications/services/openviking.hcl`. ov-ext 0.8.0 refuses
   to start while either is set, because 0.4.23+ does one recall and one
   rerank. Keep `OV_RETRIEVAL_RERANK_MAX_DOCUMENTS`: in 0.8.0 documents past
   the cap rank below every surviving rerank score.
   `ALLOWED_CUSTOM_PARAMS` in `scripts/check_openviking_config.py` already
   matches `PgVectorParams` at v0.7.0; extend the script to fail on the two
   removed variables.
3. Fix the `viking_write` description in
   `deployments/applications/services/hermes/openviking_tools/__init__.py`.
   Since OpenViking 0.5.1, `mode=create` overwrites an existing file.
4. On first boot ov-postgres reconciles the openviking_v2 table. In one
   transaction holding ACCESS EXCLUSIVE, it adds the md5 and ACL columns and
   their indexes, and installs a guard trigger. A failed reconcile stops the
   server from starting. ov-ext's maintenance task then fills md5 for
   existing rows through VikingFS, one process at a time, every 5 minutes.
   OpenViking connects as the static `openviking` role
   (`deployments/applications/secrets.tf`), which owns the database and the
   tables it created, so it may run that DDL.

Outcome: job `openviking` runs healthy on v0.5.6-1, and `/health` reports
version v0.5.6. A reranked `find` and a reranked `search` return results. A
Hermes `viking_search` works. ov-sync-consumer and ov-dash still work against
it. `just pre_commit` and `uv run --directory cli pytest` pass.

## Problems

- P1: OpenViking runs v0.4.17.1, behind upstream v0.5.6, on extension pins that break on 0.5.x.
- P2: `openviking.hcl` sets `OV_RETRIEVAL_RERANK_MAX_CALLS` and `OV_RETRIEVAL_RERANK_FINAL`, which ov-ext 0.8.0 refuses at startup.
- P3: The Hermes `viking_write` tool tells the model `mode=create` refuses an existing file, which stopped being true in 0.5.1.

## Goals

- G1: Run current upstream OpenViking with hybrid retrieval, MMR and reflection still working.
- G2: Keep agent-facing tool descriptions true to OpenViking's behavior.

## Outcomes

### O1: Job openviking runs on v0.5.6 with ov-postgres v0.7.0 and ov-ext v0.8.0
- kind: behaviour
- goal: G1
- fixes: P1
- needs: O2
- touches: `deployments/applications/services.tf`, `deployments/applications/services/openviking/Dockerfile.openviking`, `new:cli/tests/test_openviking_version.py`
- checked by: `just verify` beside the Dockerfile, a healthy deployment, `/health` version, a reranked `find` and `search`, and a Hermes `viking_search`
- seen by: operator

### O2: openviking.hcl sets only the ov-ext settings 0.8.0 reads
- kind: support
- goal: G1
- fixes: P2
- needs: none
- touches: `deployments/applications/services/openviking.hcl`, `scripts/check_openviking_config.py`, `new:cli/tests/test_check_openviking_config.py`
- checked by: `scripts/check_openviking_config.py` failing on a removed `OV_RETRIEVAL_RERANK_*` key, and its test
- seen by: nobody

### O3: viking_write describes create as overwriting
- kind: behaviour
- goal: G2
- fixes: P3
- needs: none
- touches: `deployments/applications/services/hermes/openviking_tools/__init__.py`
- checked by: `cli/tests/test_hermes_openviking_tools.py`
- seen by: calling code

## Could invalidate this plan

- The first boot on the live table. The reconcile holds ACCESS EXCLUSIVE on
  openviking_v2's context table while it adds columns and builds three
  indexes, and a failure stops the server from starting. The md5 backfill
  then reads every existing file through VikingFS on a 1-CPU task. If either
  takes long enough on a table of the live size to fail Nomad's healthy
  deadline, or the backfill starves request handling, the plan needs a
  maintenance window or a throttle.
  Settled by `spike:openviking-update-0-5/2`: on a 50,000-row table seeded by
  ov-postgres v0.6.0 on OpenViking 0.4.17.1, with Postgres on 1 CPU, the
  v0.7.0 reconcile took 0.62 s against a 60m healthy deadline, and the md5
  backfill filled every row in 150 s (0.6 s per 200-row batch) while a
  concurrent query kept p95 at 48 ms and event-loop lag stayed under 80 ms.
  The live row count was not measured; 45,686 objects in the old bucket puts
  50k in range, and both costs scale about linearly.
