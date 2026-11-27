---
type: eval
title: 'Eval: bifrost-ready-detach'
description: 'Definition of done for bifrost-ready-detach: 2 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T13:33:21+00:00'
slug: bifrost-ready-detach
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 42d304f8db02f5278a3b2bc45478b084f509ecc15da55c21b827f81014c2dfb0
  at: '2026-11-27T13:33:21+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: nomad_job.bifrost in deployments/applications/services.tf sets detach = false, so terraform apply waits for the Bifrost deployment before null_resource.bifrost_ready polls the gateway.
  Fails when: nomad_job.bifrost does not set detach = false
- r2 (judgment): A terraform plan of deployments/applications after the change shows no jobspec change for the bifrost job; the apply re-registers an identical spec, and the running allocation is updated in place, not restarted or replaced.
  Fails when: the plan shows the bifrost jobspec changing or the job being replaced, or the evidence is not recorded in the review
