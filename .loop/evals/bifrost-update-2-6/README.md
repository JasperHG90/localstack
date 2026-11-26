---
type: eval
title: 'Eval: bifrost-update-2-6'
description: 'Definition of done for bifrost-update-2-6: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:49:07+00:00'
slug: bifrost-update-2-6
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 823bb1f1dbf0a086226948c0bf30c5845c0775c597616dc70e336bb573bf18c4
  at: '2026-11-26T13:49:07+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: Bifrost is pinned to exactly 2.6.0 in deployments/applications/services.tf, the AirHelp-OSP/bifrost provider stays at ~>0.1.0, and scripts/bifrost_smoke.py still treats `access_not_found` as the unknown-key refusal.
  Fails when: the pin is any other version or a floating tag, the provider constraint moves, or the smoke script stops expecting `access_not_found`
- r2 (judgment): Before the apply, a dump of the bifrost config-store database is taken and copied to a name no job overwrites, and that path is recorded in .okf/components/bifrost.md, because 2.6.0 runs non-reversible store migrations.
  Fails when: no dump is taken before the apply, it sits only at a path backup-postgres overwrites, or its path is not recorded
- r3 (judgment): After the apply, job bifrost runs healthy on v2.6.0; scripts/bifrost_smoke.py passes against it (inference auth, metrics auth, the four named virtual keys, an embedding routed to embark); a bare-string rerank through the OpenViking virtual key returns 200; one chat call to Gemini returns 200; and a second terraform plan of deployments/applications changes no bifrost_virtual_key.
  Fails when: any of those fails, or its evidence is not recorded in the review
- r4 (judgment): .okf/components/bifrost.md and any other page naming the current Bifrost version say 2.6.0, and the component page notes that the 2.3.1 to 2.6.0 store migrations are one-way and that bifrost_upstream_latency_seconds no longer counts queue wait.
  Fails when: a page still names 2.3.1 as current, or either note is missing
