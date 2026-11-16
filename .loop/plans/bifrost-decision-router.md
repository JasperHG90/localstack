---
type: plan
title: 'Plan: bifrost-decision-router'
description: Add TypeSafe's Jev as a Bifrost provider and turn on the 2.3.1 Complexity Router with ollama/clef:27b as classifier, behind a dedicated virtual key.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:48:52+00:00'
slug: bifrost-decision-router
epic: null
depends_on: []
priority: null
---

# bifrost-decision-router

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

Two changes to the Bifrost gateway (2.3.1), both in the files that already
hold Bifrost; no new `.tf` file.

1. **Jev provider.** Add the built-in `typesafe` provider to the config.json
   providers in `deployments/applications/services/bifrost.hcl` with no
   `base_url`. The operator gave the endpoint
   `https://api.typesafe.ai/v1/systemone`, but in 2.3.1 the provider appends
   `/v1/systemone` and `/v1/models` to its base itself (default
   `https://api.typesafe.ai`), and any non-default base also turns off its
   built-in Jev model list (upstream core/providers/typesafe/utils.go:12-20,
   typesafe.go:52-58 at tag transports/v2.3.1). Render
   `TYPESAFE_API_KEY` into the env template from
   `secret/default/bifrost/typesafe` (field `TYPESAFE_API_KEY`), passed from
   `nomad_job.bifrost` in `deployments/applications/services.tf` like the
   other hand-seeded keys (the operator writes the secret; add it to the
   seeding comment there).
2. **Complexity Router.** Set `governance.complexity_analyzer_config` with
   classifier `ollama/clef:27b`, and add `governance.routing_rules` that map
   `complexity_tier` to `ollama/gpt-oss:120b` (simple),
   `ollama/deepseek-v4.1-flash` (medium) and `ollama/mistral-large-4`
   (hard/complex), scoped so only the new key's traffic is rerouted. Hermes,
   Memex and OpenViking keep their current routing and pay no classifier
   call: a priority-0 global rule `virtual_key_name != "router"` with target
   `{"weight": 1}` (keep the requested provider and model) sits ahead of the
   three tier rules, because Bifrost computes `complexity_tier` only when it
   reaches a rule that names it and stops at the first match
   (spike:bifrost-decision-router/4). The analyzer block carries non-empty
   `keywords` lists, and each virtual key `key_ids: ["*"]`.
3. **Router key.** A new `bifrost_virtual_key` in `services.tf` whose
   `ollama` entry names `clef:27b` and the three tier models explicitly,
   plus a `typesafe` entry; `provider_configs` alphabetical (see the comment
   above `bifrost_virtual_key.hermes`). The `"*"` wildcard does not work here:
   it only admits catalog models, and `clef:cloud` is not one (measured: 403
   `model_blocked` on the Hermes key, upstream
   framework/modelcatalog/models.go:316 at tag transports/v2.3.1). No
   consumer is named yet, so the key value is read from the admin UI and not
   written to Vault.
4. Record the choice with `kmctl new decision` (router scoped to one key,
   explicit model list instead of `"*"`), and update
   `.okf/components/bifrost.md` and `scripts/bifrost_smoke.py` (a decision
   call and a routed chat call) to match.

Outcome: with the router key in `x-bf-vk`, `POST /v1/decisions` to
`ollama/clef:27b` and to a `typesafe/` Jev model both return 200 with a
decision; one simple and one hard chat prompt land on `gpt-oss:120b` and
`mistral-large-4` respectively (Bifrost log or routing_info); a Hermes-key
chat request is not rerouted and makes no clef call; a second `terraform plan` of
`deployments/applications` shows no change; `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- The router cannot be set the way step 2 assumes: in 2.3.1 the analyzer
  config and routing rules may not both load from config.json under
  `source_of_truth` split with the Postgres store, the tier names may differ,
  or a global rule matched on `virtual_key_name` may not scope routing to one
  key (a `virtual_key` scope needs the key ID, which Terraform only knows
  after the job runs, and the Terraform provider has no routing-rule
  resource). Settled by spike:bifrost-decision-router/2: on 2.3.1 in split
  mode with a Postgres store and auth on, `complexity_analyzer_config` with
  `"classifier": "decision"` and `"decision": {"provider": "ollama",
  "model": "clef:cloud"}` loaded from config.json, and three global rules on
  `virtual_key_name == "router" && complexity_tier == "SIMPLE"|"MEDIUM"|"COMPLEX"`
  sent the router key to each tier model while another key kept its
  requested model. Tier values are uppercase. The analyzer block also needs
  non-empty `keywords` lists or Bifrost skips it, and each virtual key needs
  `key_ids: ["*"]`. The classifier ran on every chat request, other keys
  included, so Hermes, Memex and OpenViking would each pay one clef call per
  chat. spike:bifrost-decision-router/4 removed that cost with no key ID: a
  priority-0 global passthrough rule `virtual_key_name != "router"` ahead of
  the tier rules left 0 classifier calls for another key's three chats and 3
  for the router key's three, each on the right tier model.
- The classifier's own call to `ollama/clef:cloud` may run under the
  caller's virtual-key governance or fail on the catalog, so routing breaks
  or falls through for every request even with the explicit model list.
  Settled by spike:bifrost-decision-router/1: on a local 2.3.1 with a mock
  upstream that leaves `clef:cloud` out of its model list, all four routed
  chats made one classifier call and landed on the tier model, for a key
  naming `clef:cloud` and for a `["*"]` key alike. The classifier is an
  internal request that skips the plugin pipeline, so governance and the
  catalog never see it, though its tokens count against the caller's
  budgets. The explicit list still matters for a direct `/v1/decisions`
  call (403 on `["*"]`, 200 when named), and a config.json virtual key
  needs `key_ids: ["*"]`. Against the live gateway, the decisions route
  resolves `ollama/clef:cloud` and wants object choices and an `x-bf-vk`
  key (spike:bifrost-decision-router/3).
- The real classifier may be too slow, or a tier model name may not exist,
  so the router looks deployed but never routes. Every spike used a mock
  upstream. On a classifier timeout (default 1500 ms) or upstream error,
  Bifrost sets no tier, no tier rule matches, and router chats silently stay
  on the requested model (upstream plugins/routing/decisionclassify.go:56-111).
  The build sets `governance.complexity_analyzer_config.decision.timeout`
  from a measurement. Spike question: with an Ollama Cloud key, how long do
  `POST https://ollama.com/v1/systemone` calls to `clef:27b` with a
  three-choice complexity question take, typical and worst, and do
  `gpt-oss:120b`, `deepseek-v4.1-flash` and `mistral-large-4` answer a
  chat call on ollama.com under those exact names?
  Settled by spike:bifrost-decision-router/7, run by the operator through
  the live Bifrost with their own virtual key: five `ollama/clef:27b`
  decisions all returned 200, typical 0.5 s and worst 840 ms, with sensible
  tiers (short chat and a haiku SIMPLE, a proof MEDIUM, a distributed design
  COMPLEX), and `gpt-oss:120b`, `deepseek-v4.1-flash` and `mistral-large-4`
  each answered a chat call (`mistral-large-4` took 4.3 s). The names carry
  no cloud suffix: spike:bifrost-decision-router/5 (`clef:cloud`,
  `gpt-oss:120b-cloud`) and spike:bifrost-decision-router/6 (`clef`) got 403
  `model_blocked`. The build sets the classifier timeout to 3000 ms, over
  three times the worst call seen. That key passed `clef:27b`, so the build
  checks whether `clef:27b` is in Bifrost's catalog; if so the router key
  may use `"*"` for `ollama`, otherwise it keeps the explicit list.
