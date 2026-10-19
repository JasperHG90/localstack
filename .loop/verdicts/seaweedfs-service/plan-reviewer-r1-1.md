---
type: verdict
title: 'Verdict: seaweedfs-service plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-service: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T18:01:11+00:00'
slug: seaweedfs-service
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Fail on two blocking findings, neither of which invalidates the plan. The
approach holds, and both listed risks are settled by the cited spikes. p1:
the server's default volume limits cap the store at about 240 GiB, in a few
collections, so it is unlikely to hold six buckets and MinIO's data. p2:
the filer's unauthenticated IAM gRPC is guarded by the wrong mechanism.

## Checked

- Risk 1 (image, arch, footprint): spike 1 ran the 4.48 arm64 image with S3,
  `/healthz` on 8333 and `/metrics` on `-metricsPort`, with no OOM under a
  512 MB limit. Podman and the node's free memory are still open. The repo
  puts free memory at about 580 MB: 72 MB free before phoenix (1024 MB)
  left, then ov-dash took 512 MB (comment on `nomad_job.ov_dash` in
  deployments/applications/services.tf). A 256 to 512 MB reservation should
  place, so leaving that check to the build is reasonable.
- Risk 2 (admin identity from a rendered file): settled by spike 2. The
  file admin, IAM writes on the S3 port with `-s3.iam.readOnly=false`, and
  users made through the API all survived a restart.
- Repo claims: the minio job, volume and firewall entry in
  deployments/infrastructure/services.tf, the minio credentials in
  secrets.tf, the static `192.168.2.29:9000` Prometheus target in
  prometheus.hcl, and `_sole_tag_carrier` in
  cli/src/localstack_cli/api/services.py. That lookup confirms that leaving
  off the `s3` tag keeps the CLI route on MinIO.
- `weed server -h` on chrislusf/seaweedfs:4.48: `-volume.max` default "8",
  `-master.volumeSizeLimitMB` default 30720.

## Findings

- p1 (missing, blocking): set the volume limits (`-volume.max`,
  `-master.volumeSizeLimitMB`) so the store can hold six buckets and MinIO's
  data. A spike should confirm the setting first.
- p2 (design, blocking): the guard against the unauthenticated filer gRPC
  must be "publish only the S3 and metrics ports". The firewall rule does not
  protect anything, because the base rule already opens 20000:32000 to the
  LAN.

## Notes

STS signing key: this ticket does not need it. Spike 2 logged "no signing
key found for STS service", but the standard IAM path still worked. The
seaweedfs-workload-identity plan already owns adding the STS signing key and
`policy.defaultEffect: Deny` ("which seaweedfs-service does not set today").
