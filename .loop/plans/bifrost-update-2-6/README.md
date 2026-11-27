---
type: plan
title: 'Plan: bifrost-update-2-6'
description: Move the Bifrost gateway from 2.3.1 to 2.7.0, the latest upstream release, with embeddings, rerank, virtual keys and metrics still working.
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

Pin Bifrost at 2.7.0, the newest transports/v2.7.0 release (2026-11-27). The
pin was 2.3.1 when this ticket was planned. 2.6.0 has been live since the
first apply on 2026-11-27, and 2.7.0 shipped the same morning. The operator
chose to go on to 2.7.0 in this ticket (2026-11-27).

1. Set `bifrost_version` to `2.7.0` in `nomad_job.bifrost` in
   `deployments/applications/services.tf`. Keep the `AirHelp-OSP/bifrost`
   provider at `~>0.1.0` in `deployments/applications/providers.tf` unless
   risk 1 says otherwise.
2. Move the pin test `cli/tests/test_bifrost_version.py` to 2.7.0 with it,
   docstring included.
3. No dump. The operator told the implementer to skip the pre-apply dump
   ("Forget the backup. Just do it.", 2026-11-27), and the 2.6.0 apply has
   already run the 2.3.1 to 2.6.0 store migrations, 12 of them one-way. A dump
   taken now holds 2.6.0's schema, not 2.3.1's. 2.6.0 to 2.7.0 adds two
   migrations, both reversible. Record in `.okf/components/bifrost.md` that
   this move has no restore point to 2.3.1.
4. Update the version facts in `.okf/components/bifrost.md`.

Changes from 2.3.1 to 2.6.0 were checked against this config by reading the
upstream release notes and code at both tags (see the spikes below):
`config.json` validates against both schemas, the inference routes and the
rerank code are unchanged, the smoke script's error types and `routing_info`
fields are unchanged, and `bifrost_upstream_latency_seconds` no longer counts
queue wait (`bifrost_provider_queue_wait_seconds` does).

2.6.0 to 2.7.0, from its release notes: MCP client-credentials and AWS SigV4
auth, relay async jobs, OpenAI access programs, a fix for an MCP
refresh-token race and for usage lost on a config refresh, and two
reversible migrations that add MCP client columns. This config uses no MCP
clients and no relays.

Outcome: job `bifrost` runs healthy on image tag v2.7.0.
`scripts/bifrost_smoke.py` passes against it: inference auth, metrics auth,
the four named virtual keys and an embedding routed to embark. A bare-string
rerank through the OpenViking virtual key returns 200. One chat call to
Gemini returns 200. A second `terraform plan` of `deployments/applications`
shows no change to any `bifrost_virtual_key`. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Problems

- P1: Bifrost ran 2.3.1, four minor releases behind upstream 2.7.0.
- P2: The pin test and the component page named 2.3.1, so a moved pin fails the gate and leaves the docs wrong.
- P3: The 2.3.1 to 2.6.0 store migrations are one-way, and the operator chose no dump, so the component page must say there is no way back to 2.3.1.

## Goals

- G1: Run the current upstream Bifrost with every caller's traffic still working.
- G2: Leave an honest record of what cannot be undone.

## Outcomes

### O1: Job bifrost runs on v2.7.0 and every caller still works
- kind: behaviour
- goal: G1
- fixes: P1
- needs: O3
- touches: `deployments/applications/services.tf`
- checked by: `scripts/bifrost_smoke.py` against the new gateway, a bare-string rerank through the OpenViking key, a Gemini chat call, and a second `terraform plan` with no `bifrost_virtual_key` change
- seen by: operator

### O2: The component page says the move has no restore point to 2.3.1
- kind: support
- goal: G2
- fixes: P3
- needs: none
- touches: `.okf/components/bifrost.md`
- checked by: reading the page
- seen by: operator

### O3: The pin test and the component page name 2.7.0
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
  Re-settled for 2.7.0 by `spike:bifrost-update-2-6/5`: the same four keys,
  made on 2.3.1, kept ids and values through 2.6.0 and 2.7.0 on one Postgres
  store, planned clean on each, authenticated, and took an in-place update.
- TLS to the upstreams. 2.3.2 builds with Go 1.27.3, whose `crypto/x509`
  no longer accepts chains through some intermediates, for every TLS
  connection Bifrost makes to a provider. If ollama.com, Gemini or typesafe
  serves such a chain, calls to it fail with an x509 error. The smoke test
  would only show that after the apply has run the one-way store migrations,
  so 2.6.0 would be the wrong target and the way back would be a dump
  restore.
  Settled by `spike:bifrost-update-2-6/3`: on 2.6.0 and 2.3.1 alike, with
  the `bifrost.hcl` provider blocks and bogus keys, Gemini, typesafe and
  ollama.com each answered with an HTTP auth error after the handshake. No
  response or log line held an x509 error. A control pointed at an untrusted
  root returned `provider_connection_failed` with the x509 text, so a chain
  rejection would have shown. It ran from the devcontainer, not the cluster
  nodes.
  Re-settled for 2.7.0 by `spike:bifrost-update-2-6/6`: 2.7.0 and 2.6.0,
  both built with go1.27.4, got HTTP errors from all three upstreams after
  the handshake and no x509 error, and the untrusted-root control still
  surfaced one.
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
  Re-settled for 2.7.0 by `spike:bifrost-update-2-6/4`: on 2.7.0 and 2.6.0
  alike, the same calls returned 200 with identical forwarded bodies that
  embark v0.2.4's request models accept.
