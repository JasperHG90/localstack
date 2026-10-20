---
type: eval
title: 'Eval: bifrost-update'
description: 'Definition of done for bifrost-update: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:07:52+00:00'
slug: bifrost-update
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 94d4746fc5edb3881677a73793fdc55b2f3b50bc9e303302a1da9c819ce10b9a
  at: '2026-10-20T09:07:52+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: Bifrost is pinned to exactly v2.3.1 in deployments/applications/services.tf, the AirHelp-OSP/bifrost provider stays at ~>0.1.0, and scripts/bifrost_smoke.py treats the 2.1.0+ error `access_not_found` (not `virtual_key_not_found`) as the unknown-key refusal.
  Fails when: the pin is any other version or a floating tag, the provider constraint moves, or the smoke script still expects `virtual_key_not_found`
- r2 (judgment): Before the apply, a pg_dump of the bifrost database is taken and its location recorded, since the 2.1.0-2.3.1 store migrations cannot be undone.
  Fails when: no dump is taken before the apply, or its location is not recorded in the review
- r3 (judgment): After the apply, job bifrost runs healthy on v2.3.1, scripts/bifrost_smoke.py passes against it (inference auth, metrics auth, the four named virtual keys, an embedding routed to embark), a bare-string rerank through the OpenViking virtual key returns 200, the Grafana Bifrost dashboard shows requests after the switch, and a second terraform plan of deployments/applications changes no bifrost_virtual_key.
  Fails when: any of those fails, or the evidence is not recorded in the review
- r4 (judgment): .okf/components/bifrost.md and any docs naming the Bifrost version say 2.3.1 and note the irreversible store migration.
  Fails when: a page still names 2.0.0 as current, or the migration is not mentioned
