---
type: verdict
title: 'Verdict: seaweedfs-cutover-observability plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-cutover-observability: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:56:02+00:00'
slug: seaweedfs-cutover-observability
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk that could break this plan. Its "none" holds up: the risks it
inherits are settled by spikes in `seaweedfs-workload-identity`, and MinIO,
left untouched, is a real rollback.

## Checked

- Roles exist upstream. `seaweedfs-workload-identity` creates real per-job
  roles and policies for `tempo`, `loki` and `registry` (the probe is extra,
  not instead). Spike 4 ran the exact two client changes this plan names: the
  loki helper with `&RoleArn=..&RoleSessionName=loki`, and minio-go with
  `AWS_ROLE_ARN`. Each wrote to its own bucket and was refused on the other's
  role. Spike 4's role policies grant `s3:*` on the job's bucket, so
  multipart, list and delete calls are not cut off by action scoping, as long
  as the dependency ticket keeps that shape.
- Buckets `loki` and `tempo` come from `seaweedfs-buckets`. So does
  `data "consul_service" "seaweedfs"` in the applications root, which gives
  the endpoint template variable its source.
- Rollback is real. The plan touches no MinIO resource. The `minio` data
  source, `minio_iam_policy.*_wi` and the buckets stay, so reverting the two
  jobspecs puts both jobs back on MinIO with their old data. Data written to
  SeaweedFS in between is lost, which fits the operator's choice not to
  restore anything.
- The outcome can be measured. The tempo check asks for real objects in
  SeaweedFS's `tempo` bucket and none new in MinIO's. That catches minio-go's
  quiet fallback to anonymous credentials, which spikes 3 and 4 warn about.
- Grafana wiring: a dashboard needs a `file()` entry in
  `deployments/infrastructure/services.tf` and a template in `grafana.hcl`.
  `ScrapeJobMissing` is one `absent(...) or ...` expression. The `seaweedfs`
  scrape job comes from `seaweedfs-service`. All of this is build work.

## Findings

None.

## Notes

Left to the build:
- Ports change too. The loki helper hardcodes `:9000` in its STS URL and
  both configs hardcode `192.168.2.29:9000`. SeaweedFS answers S3 and STS on
  8333.
- Loki's local `tsdb_shipper` index may still point at chunks in MinIO. If
  Grafana shows chunk-not-found errors, they will be on time ranges that
  cross the switch. The outcome asks only for ranges after it.
- No spike has run Tempo 2.10.8 or Loki 3.4.2 end to end against SeaweedFS
  4.48: flush, multipart, compactor and retention deletes. A failure would
  show up within minutes of the loki-first switch, and MinIO is the
  rollback, so building answers this faster than a spike. If the operator
  wants it answered first, the spike question is: "Do Loki 3.4.2 and Tempo
  2.10.8, using STS session credentials for a per-job role, flush, compact
  and query back from SeaweedFS 4.48 buckets?"
