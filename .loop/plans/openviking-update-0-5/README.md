---
type: plan
title: 'Plan: openviking-update-0-5'
description: Move OpenViking from v0.4.17.1 to v0.5.6 once ov-postgres and ov-ext ship 0.5.6-compatible tags, and drop the ov-ext rerank settings 0.5.x makes redundant.
tags:
- plan
slug: openviking-update-0-5
status: draft
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

Blocked on JasperHG90/openviking_extensions issue #23 (the 0.5.6 port of
ov-postgres and ov-ext, building on #13 to #20). Promote this stub once new
`ov-postgres-v*` and `ov-ext-v*` tags exist on one commit and both suites
pass on `openviking==0.5.6`.

OpenViking runs v0.4.17.1: `openviking_base_image` and `openviking_image` in
`deployments/applications/services.tf`, built by
`deployments/applications/services/openviking/Dockerfile.openviking`, which
pins ov-postgres v0.6.0 and ov-ext v0.7.1. Both packages cap
`openviking<0.5`, and the Dockerfile's `--no-deps` install skips that cap. On
0.5.6 as-is, every reranked `find` and `search` fails, because v0.5.3 changed
what `_rerank_scores` returns.

Once the tags exist:

1. Bump `openviking_base_image` to v0.5.6, `openviking_image` to a new
   derived tag, and both git pins in `Dockerfile.openviking` to the new tags.
   The v0.5.6 image still ships python 3.13 at `/app/.venv`, so the
   `--target` path holds. Build, verify and push with the justfile beside it.
2. Remove `OV_RETRIEVAL_RERANK_MAX_CALLS` and `OV_RETRIEVAL_RERANK_FINAL` from
   `deployments/applications/services/openviking.hcl`, plus whatever else the
   new ov-ext release drops. v0.4.23 does one global recall and one rerank,
   so the call ceiling has nothing to cap, and a second final rerank would
   undo the keyword fusion. Re-derive `ALLOWED_CUSTOM_PARAMS` in
   `scripts/check_openviking_config.py` from the new `PgVectorParams`.
3. Fix the `viking_write` description in
   `deployments/applications/services/hermes/openviking_tools/__init__.py`:
   since 0.5.1, `mode=create` overwrites an existing file.
4. Before the apply, back up Postgres schema `openviking_v2` and bucket
   `openviking-v2`. No re-embedding is needed: the embedding metadata and
   record ids are unchanged.

Outcome: job `openviking` runs healthy on the new derived image. `find` and
`search` with rerank on return results, and their traces show the keyword
leg and MMR ran. One reflection sweep completes. Hermes `viking_search`
works. `just pre_commit` and `uv run --directory cli pytest` pass.

## Problems

- P1: OpenViking runs v0.4.17.1, behind upstream v0.5.6, and the extension pins it relies on break on 0.5.x.
- P2: `openviking.hcl` sets rerank knobs (`OV_RETRIEVAL_RERANK_MAX_CALLS`, `OV_RETRIEVAL_RERANK_FINAL`) that 0.5.x makes meaningless or harmful.
- P3: The Hermes `viking_write` tool tells the model `mode=create` refuses an existing file, which stopped being true in 0.5.1.

## Goals

- G1: Run current upstream OpenViking with hybrid retrieval, MMR and reflection still working.
- G2: Keep agent-facing tool descriptions true to OpenViking's behavior.

## Outcomes

### O1: Job openviking runs on v0.5.6 with the new extension tags
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `deployments/applications/services.tf`, `deployments/applications/services/openviking/Dockerfile.openviking`, `scripts/check_openviking_config.py`
- checked by: `just verify` beside the Dockerfile, a reranked `find` and `search` returning results with keyword and MMR spans, one reflection sweep, and `uv run --directory cli pytest`
- seen by: operator

### O2: openviking.hcl sets only the ov-ext settings the new release reads
- kind: support
- goal: G1
- fixes: P2
- needs: O1
- touches: `deployments/applications/services/openviking.hcl`
- checked by: `scripts/check_openviking_config.py` and a test that no removed `OV_RETRIEVAL_RERANK_*` key is set
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

- The extension port changes shape. If the 0.5.6 ports of ov-postgres or
  ov-ext need a schema migration of `openviking_v2`, a re-index, or new
  config that `ov.conf.json` cannot express, this plan grows a data
  migration step. Re-read issue #23's outcome before promoting.
