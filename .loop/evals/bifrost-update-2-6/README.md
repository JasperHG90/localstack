---
type: eval
title: 'Eval: bifrost-update-2-6'
description: 'Definition of done for bifrost-update-2-6: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T12:41:45+00:00'
slug: bifrost-update-2-6
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 68668c8caacaa19659e9fc4600b08619be26a02e435c30f6bddeeeafbb9dae6e
  at: '2026-11-27T12:41:45+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: Bifrost is pinned to exactly 2.7.0 in deployments/applications/services.tf, the AirHelp-OSP/bifrost provider stays at ~>0.1.0, and scripts/bifrost_smoke.py still treats `access_not_found` as the unknown-key refusal.
  Fails when: the pin is any other version or a floating tag, the provider constraint moves, or the smoke script stops expecting `access_not_found`
- r2 (judgment): .okf/components/bifrost.md records that the operator chose no pre-apply dump (2026-11-27); that the 2.3.1 to 2.6.0 store migrations already ran and are partly one-way, so there is no restore point to 2.3.1; and that 2.6.0 to 2.7.0 adds eight migrations, two of them one-way (widen_batch_jobs_provider_status_and_endpoint, relay_logs_add_job_debug_widen_job_status), so there is no way back to 2.6.0 without a dump of the 2.6.0 store.
  Fails when: the page claims a dump or rollback path that does not exist, omits that there is no way back to 2.3.1, or misstates which 2.6.0 to 2.7.0 migrations are one-way
- r3 (judgment): After the apply, job bifrost runs healthy on v2.7.0; scripts/bifrost_smoke.py passes against it (inference auth, metrics auth, the four named virtual keys, an embedding routed to embark); a bare-string rerank through the OpenViking virtual key returns 200; one chat call to Gemini returns 200; and a second terraform plan of deployments/applications changes no bifrost_virtual_key.
  Fails when: any of those fails, or its evidence is not recorded in the review
- r4 (judgment): .okf/components/bifrost.md and any other page naming the current Bifrost version say 2.7.0, and the component page notes that bifrost_upstream_latency_seconds no longer counts queue wait since 2.6.0.
  Fails when: a page still names 2.3.1 or 2.6.0 as current, or the latency note is missing
