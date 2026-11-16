---
type: decision
title: "ADR 0029: Bifrost routes by complexity for one virtual key and adds Jev"
description: "Only the router key goes through the clef Complexity Router, with an explicit model list, and Jev is a typesafe provider with its default base URL."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-16T08:17:22Z
status: stable
sources:
  - resource: "deployments/applications/services/bifrost.hcl"
  - resource: "deployments/applications/services.tf"
---

# ADR 0029: Bifrost routes by complexity for one virtual key and adds Jev

## Context

The operator asked for two things on Bifrost 2.3.1: Jev (TypeSafe's decision
models) as a provider, and the Complexity Router, which asks a decision model
how hard each prompt is and sends it to a cheaper or stronger model. The
classifier is Ollama's `clef:27b`. The tiers are `gpt-oss:120b` (simple),
`deepseek-v4.1-flash` (medium) and `mistral-large-4` (complex). Hermes, Memex
and OpenViking already call Bifrost with models they chose, and a classifier
call costs time on every chat.

## Decision

Only one new virtual key, `router`, is routed by complexity. A priority-0
global rule, `virtual_key_name != "router"` with target `{"weight": 1}`, comes
before the three tier rules. Bifrost computes `complexity_tier` only when it
reaches a rule that names it and stops at the first match, so every other key
keeps its model and makes no classifier call
(spike:bifrost-decision-router/4). Rejected: tier rules scoped to the router
key's ID, which work but need the ID after the key exists, so Terraform would
need a second API step, and config.json refuses an unknown ID on a fresh
store.

The router key names its four Ollama models instead of `"*"`. The wildcard
admits only models in Bifrost's catalog, and a name outside it gets 403
`model_blocked` (spike:bifrost-decision-router/5). No configured name carries
a cloud suffix: `clef:cloud` and `gpt-oss:120b-cloud` were refused, and the
plain names answered (spike:bifrost-decision-router/7).

The classifier timeout is 3 s. The slowest of five live `clef:27b` calls took
840 ms, and on a timeout Bifrost sets no tier, so the chat silently stays on
its requested model.

Jev is the built-in `typesafe` provider with no `base_url`. The provider adds
`/v1/systemone` to its base itself, and any base other than the default turns
off its built-in Jev model list. Its key is `TYPESAFE_API_KEY` at
`secret/default/bifrost/typesafe`, written by the operator like the other
provider keys.

## Consequences

- A router chat that the classifier cannot grade (timeout, error) is served
  by the model the caller asked for. `scripts/bifrost_smoke.py` checks a
  simple and a hard prompt land on their tier models when
  `BIFROST_ROUTER_VK` is set.
- The passthrough rule also matches requests with no virtual key, and marks
  them as routed by `not-router-passthrough`.
- A new tier model goes on the router key's list as well as in its rule.
  Whether the key would refuse a rule target missing from its list was not
  measured, and a direct call to that model needs the list either way.
- The router key's value is not in Vault, since nothing consumes it yet.

## Correction, 2026-11-16

The passthrough and tier rules run at priorities 10 to 13, not 0 to 3. The
store already held four global rules made by hand in the admin UI at 0 to 3,
for Claude Code's model aliases, and the first apply at 0 to 3 stopped
Bifrost at boot with `routing rule with priority 0 already exists for scope
'global'`. The passthrough still comes before the tier rules, and now after
the hand-made rules, which never name `complexity_tier`, so the choice above
holds (`bifrost-router-priorities`).
