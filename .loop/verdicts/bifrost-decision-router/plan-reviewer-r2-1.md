---
type: verdict
title: 'Verdict: bifrost-decision-router plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of bifrost-decision-router: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:02:02+00:00'
slug: bifrost-decision-router
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

No open risk could break this plan. Both round 1 findings are answered: the
Jev provider drops the base_url that doubled its path (p1), and spike 7
measured the real classifier and confirmed the tier model names on the live
gateway (p2). The plan honours the operator's constraints: Jev key at
`secret/default/bifrost/typesafe`, field `TYPESAFE_API_KEY`; classifier
`ollama/clef:27b`; tiers `gpt-oss:120b`, `deepseek-v4.1-flash`,
`mistral-large-4`; no configured name carries a cloud suffix (`clef:cloud`
appears only as the evidence for avoiding `"*"`).

## Checked

- Round 1 verdict `plan-reviewer-r1-1` and its two findings against the
  revised plan.
- Spikes 5, 6 and 7 (README, stdout, run.json). Spike 7 exited 0: five
  `clef:27b` decisions at 697, 438, 493, 840 and 548 ms with sensible tiers
  in uppercase, and 200 chat answers from all three tier models. Spikes 5
  and 6 show the suffixed and untagged names get 403, which is why the
  names are what they are.
- An unlisted risk I tested: spikes 2 and 4 ran on a fresh Postgres store,
  while the live store is already populated. Read upstream
  `transports/bifrost-http/lib/config.go` at `transports/v2.3.1`: routing
  rules merge into an existing store by ID with hash comparison (lines
  3964-3991), and `planComplexityAnalyzerConfigUpdate` merges the analyzer
  block into the stored one and writes it (lines 4145-4284, 5533-5552).
  So adding both blocks to config.json loads them on the next restart of
  the running gateway, not only on a fresh store.
- Repo: `deployments/applications/services/bifrost.hcl` already has a
  `governance` block (auth_config) to extend, and the ollama provider keys
  point at `https://ollama.com` with `models: ["*"]`, the same path spike 7
  went through. The existing virtual keys in `services.tf` use
  `allowed_models = ["*"]` and `key_ids = ["*"]` as the plan assumes.

## Findings

- p1: resolved. No base_url on the typesafe provider.
- p2: resolved. Classifier latency and tier model names measured live in
  spike 7; timeout set to 3000 ms.

## Notes

- Spike 7 measured `/v1/decisions` called directly, not the classifier's
  internal call from the routing plugin. Spike 1 showed the classifier makes
  the same `/v1/systemone` call, so the latency carries over. The outcome
  check (simple prompt on `gpt-oss:120b`, hard on `mistral-large-4`) will
  show it if not.
- Whether `clef:27b` is in the catalog (so `"*"` would work for the router
  key) is left to the build. The explicit list works either way, so this
  choice cannot break the plan.
