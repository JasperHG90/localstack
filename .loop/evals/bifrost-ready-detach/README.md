---
type: eval
title: 'Eval: bifrost-ready-detach'
description: 'Definition of done for bifrost-ready-detach: 2 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T13:24:10+00:00'
slug: bifrost-ready-detach
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 60facb9f9c166258dd6cb6e571a330fbabab8b2904f441a5e3fe4392f78f9693
  at: '2026-11-27T13:24:10+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: nomad_job.bifrost in deployments/applications/services.tf sets detach = false, so terraform apply waits for the Bifrost deployment before null_resource.bifrost_ready polls the gateway.
  Fails when: nomad_job.bifrost does not set detach = false
- r2 (judgment): A terraform plan of deployments/applications after the change does not re-register or replace the running bifrost job.
  Fails when: the plan shows the bifrost jobspec changing or the job being replaced, or the evidence is not recorded in the review
