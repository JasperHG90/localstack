---
type: eval
title: 'Eval: seaweedfs-workload-identity'
description: 'Definition of done for seaweedfs-workload-identity: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T04:37:26+00:00'
slug: seaweedfs-workload-identity
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 2c3f0194b8838f21da599be026aa487224a465d5e5d4aee64bff21f2ce5bbcd5
  at: '2026-10-20T04:37:26+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The SeaweedFS jobspec starts weed server with -s3.iam.config pointing at a rendered IAM config that sets policy.defaultEffect Deny, reads the STS signing key from default/seaweedfs/sts, names Nomad's issuer as the OIDC provider with audience seaweedfs, and gives each job in the keyless job list one role whose trust policy holds StringEquals oidc:nomad_job_id and StringLike oidc:sub global:default:<job>:* for that job, and whose policy reaches only that job's bucket.
  Fails when: the flag or the template is missing, defaultEffect is not Deny, the signing key comes from anywhere but default/seaweedfs/sts, a role's trust policy lacks either job condition or names another job, a role's policy reaches another bucket, or the provider sets policyClaim
- r2 (judgment): After the apply, batch job wi-probe with a seaweedfs-audience identity exchanges its JWT for the wi-probe role and writes to bucket wi-probe, and wi-probe-other asking for the same role gets 403. The admin key, a static-key user from seaweedfs-buckets and a second applications-root terraform plan (no changes) all still work.
  Fails when: the probe cannot write, the other probe is not refused, any static key or the clean plan breaks, or the evidence is not recorded in the review
- r3 (judgment): Both probe jobs are purged and the wi-probe role and bucket are gone from the job list and from SeaweedFS before the ticket closes.
  Fails when: nomad job status or the admin key's bucket list still shows a probe, or the job list still names wi-probe
- r4 (judgment): .okf/components/workload-identity-chain.md describes the SeaweedFS role binding and the EdDSA key trap, and a decision record says why per-job trust policies replace MinIO's claim mode, with the policyClaim comma-split bug as the rejected alternative.
  Fails when: the page or the record is missing, or either omits the binding conditions or the claim-mode bug
