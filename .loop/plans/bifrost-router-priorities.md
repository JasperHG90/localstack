---
type: plan
title: 'Plan: bifrost-router-priorities'
description: Move the router's routing rules to priorities 10-13, after the hand-made Claude Code rules at 0-3, so Bifrost boots and those rules keep working.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:58:02+00:00'
slug: bifrost-router-priorities
epic: null
depends_on: []
priority: null
---

# bifrost-router-priorities

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: bifrost-decision-router, its first apply (2026-11-16)

## Intent

The apply of `bifrost-decision-router` left Bifrost crash-looping:
`failed to sync routing rules: routing rule with priority 0 already exists for
scope 'global'`. The live config store holds four global rules made by hand
in the admin UI, at priorities 0 to 3, that send Claude Code's
`haiku-model`, `sonnet-model`, `opus-model` and `fable-model` to Ollama
models, matched on the model name and the user agent. The operator rolled
Bifrost back to job version 11 (now running as version 13).

`deployments/applications/services/bifrost.hcl` moves the router's rules to
10 (`not-router-passthrough`), 11, 12 and 13 (the SIMPLE, MEDIUM and COMPLEX
tier rules). They must come after the Claude Code rules: the passthrough
matches every request outside the `router` key, so ahead of them it would
catch Claude Code's requests and switch the aliases off. The Claude Code
rules never name `complexity_tier`, so no request pays a classifier call
before reaching ours. The Complexity Router config itself does not change.
`.okf/components/bifrost.md` notes the hand-made rules and the order.

Outcome: `cli/tests/test_bifrost_router.py` asserts every router rule's
priority is above 3, the passthrough comes first among them, and no two share
a priority; after the operator applies, Bifrost boots, the four Claude Code
rules still route, and `scripts/bifrost_smoke.py` passes with
`BIFROST_ROUTER_VK` set.

## Could invalidate this plan

- none
