---
type: plan
title: 'Plan: seaweedfs-service'
description: Run SeaweedFS with its S3 gateway as a Nomad job on orangepi4a beside MinIO, with its own volume, credentials, health check and metrics.
slug: seaweedfs-service
epic: seaweedfs-migration
priority: 2
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:25+00:00'
---

# seaweedfs-service

Relayed from: none

## Intent

Stand up SeaweedFS beside MinIO, serving nothing yet. Later tickets in the
`seaweedfs-migration` epic add buckets, keyless access and the cutover.

Add a Nomad job `new:deployments/infrastructure/services/seaweedfs.hcl`,
registered from `deployments/infrastructure/services.tf` like `minio`. It is
one `weed server` running master, volume, filer and the S3 gateway, pinned to
orangepi4a, on the podman driver. It gets:

- An image pinned to an exact SeaweedFS release no older than 4.40 (4.48 by
  `spike:seaweedfs-service/1`), started with `-s3.iam.readOnly=false` so
  Terraform can manage identities. 4.40
  fixes CVE-2026-77298 (an OIDC bearer path that skipped the role trust
  policy).
- Its own dynamic host volume `seaweedfs_data`, sized from the MinIO volume
  in `deployments/infrastructure/services.tf`.
- An admin S3 identity: a random key written to Vault KV at
  `default/seaweedfs/admin` in `deployments/infrastructure/secrets.tf`, and
  rendered into the job by a template.
- A Consul service `seaweedfs` with an HTTP health check. It does not carry
  the `s3` tag yet: the CLI resolves the `s3` route to the one service that
  carries that tag (`cli/src/localstack_cli/api/services.py`), and MinIO keeps
  it until the cutover.
- Ports opened from 192.168.0.0/16 by a firewall rule beside MinIO's in
  `deployments/infrastructure/services.tf`, and a Prometheus scrape job in
  `deployments/infrastructure/services/prometheus.hcl`.

Write `new:.okf/components/seaweedfs.md`, and a decision record for SeaweedFS
over MinIO with the alternatives (Garage, keeping MinIO built from source).

Outcome: after an apply, `nomad job status seaweedfs` shows the allocation
running and its Consul check passing. With the admin key, `aws s3 mb`,
`aws s3 cp`, `aws s3 ls` and `aws s3 rb` against the S3 port all succeed.
Prometheus shows `up{job="seaweedfs"} == 1`. MinIO is unchanged. `just
pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- The pinned image does not run on orangepi4a under podman (arm64, the node's
  kernel and memory next to MinIO's 2560 MB). If it does not, the store moves
  to another node and the whole epic's placement changes.
  Settled by `spike:seaweedfs-service/1`: image chrislusf/seaweedfs tag 4.48
  (arm64) ran `weed server -s3` under a 512 MB limit, peaking at 220 MB RSS.
  Health is `GET /healthz` on the S3 port 8333. Metrics are `/metrics` on the
  port set by `-metricsPort`. Docker, not podman, and orangepi4a's free RAM is
  not recorded: building checks free memory on the node before it sets the
  job's `memory`.
- The admin identity cannot be supplied from a file or env the job renders
  from Vault. If SeaweedFS keeps identities only in its filer and expects them
  to be created through `weed shell` after start, then the first identity
  needs a bootstrap step outside Terraform, and this plan changes shape.
  Settled by `spike:seaweedfs-service/2`: an admin identity in the file
  passed to `-s3.config` works, the embedded IAM API on the S3 port accepts
  CreateUser, CreateAccessKey and PutUserPolicy once the server runs with
  `-s3.iam.readOnly=false`, and API-made users survive a restart beside the
  file's admin. The filer's IAM gRPC has no auth unless
  `jwt.filer_signing.key` is set, so the firewall rule opens only the S3 and
  metrics ports, never the master, volume or filer ports.
