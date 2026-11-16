---
type: verdict
title: 'Verdict: bifrost-decision-router reviewer round 1'
description: 'reviewer verdict for round 1 of bifrost-decision-router: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:31:32+00:00'
slug: bifrost-decision-router
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says. The config.json router block matches the
spike 4 config that worked (same keyword shape, same rule order and CEL, with
the suffix-free names from spike 7). The timeout "3s" parses under upstream
ComplexityDecisionConfig.UnmarshalJSON at transports/v2.3.1. jev-latest is in
the static typesafe catalog. The Jev secret already exists in Vault, so the
new template block will not hold the alloc. There are two non-blocking gaps:
the live smoke cannot prove the "no classifier call" claim (f1), and the r3
suffix scan is narrower than the row (f2).

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass,
  rows r1-r4 pass, "stamp green: e40a0c02f7b8...e42".
- `scripts/tf_validate.sh`: deployments/applications "Success! The
  configuration is valid." The router key's allowed_models are alphabetical
  and its provider_configs are in order, so a second plan should be clean.
- Missing-secret risk: consul-template's `with secret` on a missing KV v2 path
  errors and blocks the render. Bifrost has a static port and a pinned host,
  so applying before the secret existed would take the gateway down. I
  checked `vault kv metadata get secret/default/bifrost/typesafe`: version 1
  was created 2026-11-15 by userpass-operator, and the field set is exactly
  ['TYPESAFE_API_KEY']. The path is under the job's own default/bifrost/
  prefix, like the other provider keys. The risk does not apply here.
- Re-registering the job: the jobspec edit is intended. It restarts Bifrost
  once, and `null_resource.bifrost_ready` re-polls /health through its
  jobspec hash before any virtual key is touched. That is the existing
  pattern.
- Upstream source at transports/v2.3.1 (scratchpad checkout): the decision
  timeout accepts a duration string, and the typesafe catalog lists
  jev-latest.
- Spike shapes: the smoke's decision body matches spike 7's ollama_live.sh,
  and the routing_info.model values match spike 4's output (bare model name,
  no provider prefix). The Hermes check expects "deepseek-v4.1-flash", which
  is right.
- Rows: r1, r2 and r3 tests parse the real heredoc and Terraform and assert
  each fails_when clause, except the r3 gap in f2. The stub-HTTP tests cover
  both branches of the router and Hermes smoke checks.
- r5 (judgment): the config can meet the decisions, tier-routing and
  plan-clean parts, and the smoke covers decisions, the two tier prompts and
  the Hermes model. It cannot show "no clef call" for Hermes (f1).
- r6 (judgment): ADR 0029 exists with the alternative it rejected. The
  component page and the smoke docstring match the config.

## Findings

- f1: the Hermes smoke check passes even when the classifier runs for Hermes.
  Assert no 'decisions' entry in extra_fields.routing_metadata.calls for the
  Hermes chat, and assert one is present for the router chats.
- f2: widen the r3 cloud-suffix scan to every virtual key block in
  services.tf and every provider key's `models` in the jobspec.

## Notes

ADR 0029 says a new tier model must also go on the router key's list "or the
key refuses it". No spike tested a routed target outside the key's list,
because every spike key listed all the tier models. The advice is harmless,
but the claim is untested.
