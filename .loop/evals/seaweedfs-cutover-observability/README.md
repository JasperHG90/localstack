---
type: eval
title: 'Eval: seaweedfs-cutover-observability'
description: 'Definition of done for seaweedfs-cutover-observability: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T04:37:29+00:00'
slug: seaweedfs-cutover-observability
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: cf707507a63bb6aa02e26bddcbb4874623caf445cd8fdbeda2323bc7b3772f77
  at: '2026-10-20T04:37:29+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: tempo.hcl and loki.hcl request a workload identity with audience seaweedfs and take their S3 and STS endpoint from a template variable, tempo sets AWS_ROLE_ARN to the tempo role, and loki's credential_process helper sends RoleArn for the loki role and RoleSessionName=loki.
  Fails when: either jobspec keeps audience minio, hardcodes 192.168.2.29:9000, tempo lacks AWS_ROLE_ARN, or loki's helper lacks RoleArn or RoleSessionName
- r2: Grafana's alert rules hold a ScrapeJobMissing entry for the seaweedfs scrape job, and a SeaweedFS dashboard sits beside MinIO's.
  Fails when: the seaweedfs ScrapeJobMissing entry or the dashboard file is missing, or MinIO's are removed
- r3 (judgment): After the applies, loki and tempo are healthy, SeaweedFS's loki and tempo buckets gain objects across two readings, Grafana returns logs and traces for a range after the switch, MinIO's loki and tempo object counts stay fixed, and the SeaweedFS dashboard and alert rules load without errors.
  Fails when: a job is unhealthy, a SeaweedFS bucket stays empty or flat, a query returns nothing after the switch, MinIO's counts rise, or the evidence is not recorded in the review
