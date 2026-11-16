---
type: eval
title: 'Eval: bifrost-decision-router'
description: 'Definition of done for bifrost-decision-router: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T08:02:39+00:00'
slug: bifrost-decision-router
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 0e4a429292e21ea9a4beed6007ac292dd08545d67e06e7c3e052f34b2067c77d
  at: '2026-11-16T08:02:39+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the rendered Bifrost config.json has a typesafe provider with no base_url whose key comes from env TYPESAFE_API_KEY, and the env template reads TYPESAFE_API_KEY from secret/default/bifrost/typesafe
  Fails when: the typesafe provider is missing, carries a base_url, reads its key from anywhere else, or the env template does not render TYPESAFE_API_KEY from that path and field
- r2: the complexity analyzer uses ollama/clef:27b with non-empty keyword lists, and the routing rules send simple, medium and complex tiers to ollama/gpt-oss:120b, ollama/deepseek-v4.1-flash and ollama/mistral-large-4, behind a priority-0 rule that passes every virtual key but router through unchanged
  Fails when: the classifier or a tier model differs, a keyword list is empty, a tier rule can match a key other than router, or the passthrough rule is missing or does not come first
- r3: no model name in the Bifrost jobspec or the virtual keys in services.tf carries a cloud suffix, and the router virtual key lists clef:27b and the three tier models explicitly with a typesafe entry, provider_configs in alphabetical order
  Fails when: any configured model name ends in :cloud or -cloud, the router key uses "*" for ollama, lacks one of the four models or the typesafe entry, or its provider_configs are out of order
- r4: the repo gates and the CLI test suite pass
  Fails when: just pre_commit or uv run --directory cli pytest exits non-zero
- r5 (judgment): after the operator writes the Jev secret and applies, with the router key in x-bf-vk: /v1/decisions to ollama/clef:27b and to a typesafe Jev model both return 200; a simple and a hard chat prompt land on gpt-oss:120b and mistral-large-4; a Hermes-key chat request is not rerouted; a second terraform plan of deployments/applications shows no change
  Fails when: any of those is not shown by scripts/bifrost_smoke.py output, Bifrost routing info or the plan
- r6 (judgment): a decision record, .okf/components/bifrost.md and scripts/bifrost_smoke.py describe what was built
  Fails when: the decision is missing, or the component page or smoke script disagrees with the config
