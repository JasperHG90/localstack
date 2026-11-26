---
type: plan
title: 'Plan: bifrost-update-2-6'
description: Move the Bifrost gateway from 2.3.1 to 2.6.0, the latest upstream release, with embeddings, rerank, virtual keys and metrics still working.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:30:29+00:00'
slug: bifrost-update-2-6
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# bifrost-update-2-6

Relayed from: none

## Intent

Pin Bifrost at 2.6.0, the newest transports/v2.6.0 release
(2026-11-19). The image docker.io/maximhq/bifrost:v2.6.0 ships linux/arm64 for radxa.
The pin today is 2.3.1.

1. Set `bifrost_version` to `2.6.0` in `nomad_job.bifrost` in
   `deployments/applications/services.tf`. Keep the `AirHelp-OSP/bifrost`
   provider at `~>0.1.0` in `deployments/applications/providers.tf` unless
   risk 1 says otherwise.
2. Move the pin test `cli/tests/test_bifrost_version.py` to 2.6.0 with it,
   docstring included.
3. Before the apply, dump the `bifrost` config-store database and copy the
   dump to a name no job overwrites, as `bifrost-update` did. 2.3.1 to 2.6.0
   adds 39 config-store migrations, 12 of them marked non-reversible. They
   only add columns, tables and indexes, and 2.3.1's migrator ignores unknown
   migrations, so a 2.3.1 binary should still start on the migrated store.
   Nobody has run that, so the dump is the rollback.
4. Update the version facts and the rollback dump path in
   `.okf/components/bifrost.md`.

Changes from 2.3.1 to 2.6.0, checked against this config by reading the
upstream release notes and code at both tags:

- The `config.json` that `deployments/applications/services/bifrost.hcl`
  renders validates against both tags' upstream transports/config.schema.json with 0
  errors. The complexity router and `complexity_tier` are deprecated for v3
  and keep working in 2.x.
- Inference routes `/v1/chat/completions`, `/v1/embeddings`, `/v1/rerank` and
  `/v1/decisions` are unchanged. The rerank schema and the OpenAI rerank
  provider code have zero diff, so OpenViking's bare-string rerank (ADR
  `.okf/decisions/0008-openviking-rerank-goes-through-bifrost.md`) still holds.
- `scripts/bifrost_smoke.py` stays as is. The `access_not_found` and
  `virtual_key_required` error types and the `routing_info` fields it reads
  are unchanged.
- 2.6.0 rejects a virtual key that names the same provider twice with a 400.
  None of the four keys in `services.tf` does.
- 2.6.0 stops counting queue wait in `bifrost_upstream_latency_seconds` and
  moves it to `bifrost_provider_queue_wait_seconds`. The latency panels in
  `deployments/infrastructure/services/grafana/bifrost.json` read lower after
  the switch. Every series the dashboard queries still exists.
- 2.3.2 builds with Go 1.27.3, whose `crypto/x509` rejects some intermediate
  chains. Only a live call to each upstream (Ollama Cloud, Gemini, typesafe)
  shows whether this bites.

Outcome: job `bifrost` runs healthy on image tag v2.6.0.
`scripts/bifrost_smoke.py` passes against it: inference auth, metrics auth,
the four named virtual keys and an embedding routed to embark. A bare-string
rerank through the OpenViking virtual key returns 200. One chat call to
Gemini returns 200. A second `terraform plan` of `deployments/applications`
shows no change to any `bifrost_virtual_key`. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Problems

- P1: Bifrost runs 2.3.1, three minor releases behind upstream 2.6.0.
- P2: The pin test and the component page name 2.3.1, so a moved pin fails the gate and leaves the docs wrong.

## Goals

- G1: Run the current upstream Bifrost with every caller's traffic still working.
- G2: Keep a way back if the one-way store migrations go wrong.

## Outcomes

### O1: Job bifrost runs on v2.6.0 and every caller still works
- kind: behaviour
- goal: G1
- fixes: P1
- needs: O2
- touches: `deployments/applications/services.tf`
- checked by: `scripts/bifrost_smoke.py` against the new gateway, a bare-string rerank through the OpenViking key, a Gemini chat call, and a second `terraform plan` with no `bifrost_virtual_key` change
- seen by: operator

### O2: A dump of the bifrost store, taken before the apply, sits at a name no job overwrites
- kind: support
- goal: G2
- fixes: P1
- needs: none
- touches: `.okf/components/bifrost.md`
- checked by: the dump's object listed in the backup bucket and its path recorded in the component page
- seen by: operator

### O3: The pin test and the component page name 2.6.0
- kind: support
- goal: G1
- fixes: P2
- needs: none
- touches: `cli/tests/test_bifrost_version.py`, `.okf/components/bifrost.md`
- checked by: `uv run --directory cli pytest`
- seen by: calling code

## Could invalidate this plan

- Provider against the new store. `AirHelp-OSP/bifrost` 0.1.1 manages the
  four virtual keys. Static reading says the 2.6.0 API is compatible: the
  create and update bodies only gained optional fields, and the provider
  ignores unknown JSON. But `services.tf` relies on `provider_configs`
  coming back in alphabetical order, and 2.6.0 changes how provider config
  hashes are computed. If keys made on 2.3.1 show drift, lose their values
  or fail auth once the same store is migrated to 2.6.0, the provider must
  move to a newer major, which can change resource schemas and state.
  Settled by `spike:bifrost-update-2-6/2`: provider 0.1.1 made the four
  `services.tf` keys on 2.3.1 with a Postgres store. After 2.6.0 migrated
  that store, the keys kept their ids and values, `provider_configs` still
  came back in alphabetical order, and `terraform plan -detailed-exitcode`
  exited 0. The keys authenticated, and an in-place update applied and
  planned clean. The provider stays at `~>0.1.0`.
- Rerank and embeddings through embark. OpenViking needs bare-string rerank
  documents accepted at the gateway and forwarded to the `openai`-based
  custom provider `embark` in a shape embark takes. The rerank code has zero
  diff, but the 2.4.0 model catalog and list-models changes sit on the same
  path. If 2.6.0 breaks either call, the target version is wrong and the pin
  stops at an earlier 2.x.
  Settled by `spike:bifrost-update-2-6/1`: on 2.6.0 and 2.3.1 alike, a
  bare-string rerank through a virtual key returned 200 and reached a stub on
  the deployed embark v0.2.4 image as identical `{"text": ...}` documents
  that embark's own request models accept. Embeddings reported `embark` in
  `routing_info`.
