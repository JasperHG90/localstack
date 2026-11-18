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
- Only two ports leave the host: S3 (with the embedded IAM API) and metrics.
  Master, volume and filer, and their gRPC ports, are neither mapped to Nomad
  ports nor bound off loopback. The worker base rule in
  `bootstrap/playbooks/configure_network.yml` already opens 20000:32000 to
  the LAN, and podman's published ports skip ufw, so a firewall rule alone
  cannot hide them, and the filer's IAM gRPC has no auth. The two ports get a
  firewall rule beside MinIO's in `deployments/infrastructure/services.tf`,
  and metrics get a scrape job in
  `deployments/infrastructure/services/prometheus.hcl`.
- Volume limits set for the store's real size. The defaults
  (`-volume.max` 8, `-master.volumeSizeLimitMB` 30720) cap it near 240 GiB
  however large the host volume is, and S3 puts each bucket in its own
  collection that grows several volumes at once, so eight slots can run out
  with six buckets.

Write `new:.okf/components/seaweedfs.md`, and a decision record for SeaweedFS
over MinIO with the alternatives (Garage, keeping MinIO built from source).

Outcome: after an apply, `nomad job status seaweedfs` shows the allocation
running and its Consul check passing. With the admin key, `aws s3 mb`,
`aws s3 cp`, `aws s3 ls` and `aws s3 rb` against the S3 port all succeed,
and six buckets made in a row each take a write. From another LAN host, only
the S3 and metrics ports answer on orangepi4a among SeaweedFS's ports.
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
- Volume slots. If six buckets cannot each take a write under limits that
  also leave room for MinIO's data (registry alone is 5.34 GB), the
  single-node `weed server` layout needs another shape (separate volume
  servers, or a larger slot count with smaller volumes) before buckets can be
  made on it.
  Settled by `spike:seaweedfs-service/3`: under defaults only 4 of 6 buckets
  took a first write, because the master grows 7 volumes per collection
  (`copy_1 = 7`). With `-volume.max=0 -master.volumeSizeLimitMB=1024
  -master.volumePreallocate=false` and a `master.toml` holding
  `[master.volume_growth] copy_1 = 2`, all six wrote and 300 MiB fit, with 2
  slots per bucket. Binding works with `-ip=127.0.0.1 -ip.bind=127.0.0.1
  -s3.ip.bind=0.0.0.0 -metricsIp=0.0.0.0`: master, volume and filer listen on
  loopback only. The S3 gRPC port (S3 port + 10000) follows `-s3.ip.bind` and
  cannot be turned off, so the firewall rule must leave it closed, and the
  job maps no Nomad port to it.
