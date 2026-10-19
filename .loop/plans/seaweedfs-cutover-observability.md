---
type: plan
title: 'Plan: seaweedfs-cutover-observability'
description: Move Tempo and Loki to empty SeaweedFS buckets with keyless per-job credentials, and give SeaweedFS its own Grafana dashboard and alerts.
slug: seaweedfs-cutover-observability
epic: seaweedfs-migration
depends_on:
- seaweedfs-workload-identity
priority: 5
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:52:57+00:00'
---

# seaweedfs-cutover-observability

Relayed from: none

## Intent

Switch the two observability stores to SeaweedFS. They keep 30 days of
data, so they start on empty buckets and nothing is restored (operator,
2026-10-19). MinIO keeps running untouched as the rollback.

- `deployments/applications/services/tempo.hcl`: identity audience
  `seaweedfs`, `AWS_ROLE_ARN` set to the tempo role from
  `seaweedfs-workload-identity`, and the STS and S3 endpoints on SeaweedFS.
  The hardcoded `192.168.2.29:9000` becomes a template variable from
  `deployments/applications/services.tf`.
- `deployments/applications/services/loki.hcl`: the same audience and
  endpoints, and the `credential_process` helper adds
  `&RoleArn=<loki role>&RoleSessionName=loki` to its STS query string.
  Switch loki first and check it before tempo.
- Grafana: a SeaweedFS dashboard and alert rules for its own metrics, beside
  MinIO's, under `deployments/infrastructure/services/grafana/`, and a
  `ScrapeJobMissing` entry for the `seaweedfs` scrape job in
  `deployments/infrastructure/services/grafana/alert-rules.yaml`.

Outcome: after the applies, `nomad job status` shows loki and tempo
healthy. Since the switch, SeaweedFS's `loki` bucket holds new chunks and
its `tempo` bucket new blocks (object counts above zero and rising), Grafana
queries both for a time range after the switch, and MinIO's `loki` and
`tempo` buckets get no new objects. The SeaweedFS dashboard renders, and its
alert rules load with no errors. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- none
