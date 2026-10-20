---
type: plan
title: 'Plan: bifrost-update'
description: Move the Bifrost gateway from 2.0.0 to 2.3.1, the latest upstream release, with embeddings, rerank, virtual keys and metrics still working.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:09:48+00:00'
slug: bifrost-update
epic: null
depends_on: []
priority: null
---

# bifrost-update

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none
<!-- When this ticket carries a finding raised while building another ticket,
replace "none" with that ticket's slug and the finding, in one line (ADR 0001). -->

## Intent

Pin Bifrost at 2.3.1, the newest transports/v2.3.1 release and
docker.io/maximhq/bifrost:v2.3.1 tag (published 2026-10-19, arm64 image
present for radxa). The pin today is 2.0.0.

1. Set `bifrost_version` to `2.3.1` in `nomad_job.bifrost` in
   `deployments/applications/services.tf`. Keep the `AirHelp-OSP/bifrost`
   provider at `~>0.1.0` in `deployments/applications/providers.tf` unless
   risk 1 says otherwise.
2. Before the apply, `pg_dump` the `bifrost` config-store database. The
   2.1.0 to 2.3.1 migrations are not reversible (2.3.1 drops columns,
   2.3.0 builds unique indexes on `governance_virtual_keys.value_hash`), so
   rolling back to 2.0.0 means restoring that dump.
3. Fix `scripts/bifrost_smoke.py` for 2.1.0's rename of the governance error
   `virtual_key_not_found` to `access_not_found`. Its auth probe would fail
   on the new gateway otherwise.
4. Update the version facts in `.okf/components/bifrost.md` (image tag,
   version history) and keep the ">= 2.0.0" claim in
   `deployments/applications/services/openviking.hcl` as is: it is still
   true, and editing a jobspec comment re-registers the job.

Changes between 2.0.0 and 2.3.1 checked against this config, from the
upstream release notes:

- Config keys in `deployments/applications/services/bifrost.hcl`: 2.2.6
  turns `enforce_auth_on_inference` on by default and adds a setup-token lock
  that applies only while dashboard auth is off. This config sets both
  explicitly (`governance.auth_config` on, `enforce_auth_on_inference: true`),
  so neither changes behavior. `allow_private_network` and
  `custom_provider_config` keep their names.
- Rerank: 2.1.0 sends rerank documents to Cohere-based custom providers as
  bare strings. embark is an `openai`-based custom provider, and the gateway
  edge still accepts bare strings from OpenViking (ADR
  `.okf/decisions/0008-openviking-rerank-goes-through-bifrost.md`).
- Admin API used by the provider: 2.3.0 makes `PUT
  /api/governance/virtual-keys/{id}` without `key_ids` keep the key
  associations instead of dropping them, and 2.3.1 adds a `metadata` field
  to virtual keys.
- Metrics read by `deployments/infrastructure/services/grafana/bifrost.json`:
  no `bifrost_*` series renamed. 2.3.0 adds an `app` label on request
  metrics, which the dashboard's `sum by` queries absorb.

Outcome: job `bifrost` runs healthy on image tag v2.3.1;
`scripts/bifrost_smoke.py` passes against it (inference auth, metrics auth,
the four named virtual keys, an embedding routed to embark), and a rerank
call with bare-string documents through an OpenViking virtual key returns
200; the Grafana Bifrost dashboard shows request rate after the switch; a
second `terraform plan` of `deployments/applications` shows no change to any
`bifrost_virtual_key`; `just pre_commit` and `uv run --directory cli pytest`
pass.

## Could invalidate this plan

- Provider against the new API. `AirHelp-OSP/bifrost` 0.1.1 (May 2026) predates
  Bifrost 2.0.0 and runs fine on it today. If 2.3.1's virtual key responses (the new
  `metadata` field, the `key_ids` change, the `value_hash` index) make it
  show drift or fail the post-apply consistency check, the ticket must also
  move the provider to 0.4.x, which can change resource schemas and state.
  Settled by `spike:bifrost-update/1` (keys made fresh on 2.3.1) and
  `spike:bifrost-update/4` (keys made on 2.0.0, store migrated to 2.3.1 on
  the same Postgres database): provider 0.1.1 plans clean, keys keep their
  ids and values and authenticate, and an in-place update applies. The
  provider stays at `~>0.1.0`.
- Rerank and embeddings through embark. OpenViking needs bare-string rerank
  documents accepted at the gateway and forwarded to an `openai`-based custom
  provider in a shape embark takes, and the 2.1.0 rerank change could alter
  what reaches embark. If 2.3.1 breaks either call, the target version is
  wrong and the pin must stop at an earlier 2.x.
  Settled by `spike:bifrost-update/3`: on 2.3.1 and 2.0.0 alike, a
  bare-string rerank returned 200 and reached embark as identical
  `{"text": ...}` documents that embark v0.2.1's own request models accept,
  and embeddings report `embark` in `routing_info`.
