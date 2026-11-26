---
type: verdict
title: 'Verdict: bifrost-update-2-6 plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of bifrost-update-2-6: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-26T13:54:15+00:00'
slug: bifrost-update-2-6
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach holds. Both listed risks are settled by spikes whose evidence
answers them. One upstream-reachability risk the plan itself names is not
settled and is cheap to check before the one-way migration (p1). The 2.0
facts also mis-state two dependencies a split would act on (p2, p3). Fail,
revise, look again.

## Checked

- Spike 1 (`.loop/spikes/bifrost-update-2-6/1/`): exit 0. stdout shows 2.3.1
  and 2.6.0 both return 200 on bare-string rerank and embeddings, routing_info
  names embark, and the forwarded rerank bodies are byte-identical and pass
  embark's own request models. Answers risk 2. Limits (stub upstream, sqlite)
  do not touch the risk as stated.
- Spike 2 (`.loop/spikes/bifrost-update-2-6/2/`): exit 0, `RESULT: clean`.
  Provider 0.1.1 keys made on 2.3.1 with Postgres keep ids and values after
  2.6.0 migrates the store, provider_configs stay alphabetical, plan exits 0
  before and after an in-place update, auth behaves the same. Answers risk 1.
- `deployments/applications/services.tf:902` pins 2.3.1;
  `providers.tf` holds `~>0.1.0`; `cli/tests/test_bifrost_version.py` pins
  2.3.1 exactly and checks the provider and `access_not_found`.
- `scripts/bifrost_smoke.py` calls ollama and typesafe live (decisions,
  router chats), so the x509 question would surface only after the apply.
- `.okf/components/bifrost.md` has the earlier dump path to update.
- Eval rows r1 to r4 match the outcomes.

## Findings

- p1: the Go 1.27.3 x509 risk is named in the prose but not settled or
  accepted, and a local 2.6.0 container can answer it before the one-way
  migration. Spike question given in the claim.
- p2: O1 cannot ship without the pin-test change in O3; `needs` omits it.
- p3: O2 points at P1, which it does not fix; the one-way-migration problem
  it does answer is missing from Problems.

## Notes

The 2.3.1 binary starting on a migrated store is unverified, but the plan
does not rely on it: the dump is the stated rollback, as in `bifrost-update`.
The latency metric change is recorded and covered by r4. No split needed.
