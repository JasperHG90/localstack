---
type: decision
title: "ADR 0016: SeaweedFS replaces MinIO for object storage"
description: "MinIO is end of life and its published image no longer downloads, so the cluster's S3 store moves to a single-node SeaweedFS on orangepi4a, over Garage and over running MinIO built from source."
tags: [adr, decision, seaweedfs, minio, s3, object-storage]
generated:
  by: claude-opus/5.5
  at: 2026-10-19T00:00:00Z
status: stable
sources:
  - resource: "deployments/infrastructure/services/seaweedfs.hcl"
  - resource: "deployments/infrastructure/services/minio.hcl"
---

# ADR 0016: SeaweedFS replaces MinIO for object storage

## Context

MinIO runs every bucket on the cluster: the registry, OpenViking, Loki,
Tempo, models and the data lake. Upstream has ended the community edition.
On 2026-10-19 the image the cluster pins,
`minio/minio:RELEASE.2025-09-07T16-13-09Z`, returned 404 on Docker Hub and
401 on quay, and dl.min.io returned 410. If orangepi4a loses its cached
copy, MinIO cannot start again.

Three jobs reach MinIO without a stored key. Each exchanges its Nomad
workload identity JWT at MinIO's STS, and MinIO applies the policy named by
the token's `nomad_job_id` claim. A replacement has to keep that per-job
isolation.

## Decision

Move to SeaweedFS, one `weed server` on orangepi4a, beside MinIO until the
cutover. Spikes on 4.48 showed it holds what the cluster relies on:

- Per-job keyless access through STS roles whose trust policy matches
  `oidc:nomad_job_id` and `oidc:sub`. A token for another job is refused.
  Its MinIO-like claim mode (`policyClaim`) is not used, because it splits
  the claim on commas and a job id `evil,tempo` got tempo's policy.
- Per-bucket isolation for static keys, managed by the `hashicorp/aws`
  provider through its embedded IAM API with a clean second plan.
- Registry blobs restored through rclone serve by tag and by digest.

Rejected:

- **Garage.** It has no STS, so every job would go back to a static key,
  which reverses the workload identity work.
- **MinIO built from source.** It keeps the claim-mode setup working, but
  makes the cluster build and patch an unmaintained server itself.

## Consequences

- Each keyless job needs a role and must send `RoleArn` and
  `RoleSessionName`. minio-go sends them only when `AWS_ROLE_ARN` is set, and
  falls back to anonymous credentials without it, quietly.
- The server's safe shape depends on flags that fail quietly when dropped,
  so a drift test pins them ([SeaweedFS](/components/seaweedfs.md)).
- Data moves through the GCS backup, not store to store, so the backup job
  covers every durable bucket first.
