---
type: plan
title: 'Plan: minio-removal'
description: Remove MinIO, its Terraform provider and resources, its volume, routes, monitoring and docs once nothing uses it.
slug: minio-removal
epic: seaweedfs-migration
depends_on:
- seaweedfs-cutover
priority: 6
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:35+00:00'
---

# minio-removal

Relayed from: none

## Intent

After the cutover nothing reads or writes MinIO. Remove it, so the cluster
stops running end-of-life software and the next reader does not have to ask
which store is live.

How the MinIO resources leave Terraform state. Nothing is destroyed on
MinIO itself: `minio_s3_bucket` has no `force_destroy`, the buckets still
hold objects, and the data stays until `minio-volume-destroy`. Instead, every
`minio_*` resource and `module.buckets` in the applications root get a
`removed { from = ...; lifecycle { destroy = false } }` block, which drops
them from state and leaves MinIO untouched. The applications root's
`provider "minio"` reads its address from `data.consul_service.minio` and
its login from the Vault key `default/minio/localstack`, both of which the
later steps delete, so the order is fixed:

1. Applications root, in two commits (`spike:minio-removal/2`):
   - A: add the `removed` blocks, delete the `minio_*` resources, the
     `deployments/applications/modules/bucket` module and the MinIO keys in
     `deployments/applications/secrets.tf`. Keep `required_providers.minio`,
     but give `provider "minio"` static dummy values (an unreachable
     `minio_server`, dummy user and password) and delete the
     `data "consul_service" "minio"` lookup and the root-key read in
     `deployments/applications/services.tf`. Apply: state loses every MinIO
     address, and the provider never contacts MinIO.
   - B: delete `provider "minio"` and its `required_providers` entry, run
     `terraform init` (the lock file follows), and `terraform plan` reports
     no changes.
2. Infrastructure root: delete `nomad_job.minio`, its jobspec
   `deployments/infrastructure/services/minio.hcl`, its firewall rule, the
   Vault KV root key and `random_password.minio_secret_key`, MinIO's
   dashboard, alerts and scrape job, and the `minio.lab` edge route. Apply.
3. Playbook: drop the Consul `deploy` policy's `service "minio"` grant in
   `bootstrap/playbooks/enable_consul_secrets.yml`, and run it.
4. Devcontainer: drop `mc` from `.devcontainer/Dockerfile` and its alias in
   `.devcontainer/bootstrap.sh`, and the stale MinIO entries in
   `bootstrap/.env.example` and `bootstrap/README.md`.
5. Applications root: delete the old backup key path (see the backup job
   below). Apply.

The backup job. The cutover leaves it reading SeaweedFS under its old name.
Rename it here: `nomad_job.backup_minio` and
`deployments/infrastructure/services/backup-minio.hcl` become `backup_s3` and
`backup-s3.hcl`. A job with a bare `vault {}` reads only
`secret/data/default/<job id>/*`, so every secret it reads moves with it, in
the step order above:

- Step 1A also writes the SeaweedFS backup key at `default/backup-s3/seaweedfs`
  from `deployments/applications/secrets.tf`, beside the
  `default/backup-minio/seaweedfs` copy that `seaweedfs-buckets` made, so the
  old job keeps its key until it is gone.
- Step 2 moves the GCS key to `default/backup-s3/gcs` in
  `deployments/infrastructure/secrets.tf`, registers `backup-s3`, and runs
  `nomad job stop -purge backup-minio`, because `nomad_job` here sets no
  `purge_on_destroy` and a stopped periodic job otherwise lingers.
- Step 5, after step 2: an applications-root apply deletes
  `default/backup-minio/seaweedfs`. `cli/tests/test_backup_coverage.py` and
`cli/tests/test_health_rules.py` follow the rename. The GCS prefix `minio/`
stays as it is, so the backup history carries on. It is the one MinIO name
left in the code on purpose, and the jobspec says why in one comment.

The `minio_data` host volume and the data on it stay. Destroying them is the
one irreversible step, and it is the stub `minio-volume-destroy`, which only
the operator promotes.

Docs: replace the three MinIO keyless how-tos with SeaweedFS ones (or one
page if the two client routes have merged), update
`docs/explanation/workload-identity.md`, and mark
`.okf/components/minio.md` superseded with a link to the SeaweedFS
component page that `seaweedfs-service` writes. Write a decision record for
the removal.

Outcome, all true at once:

- `grep -rni minio deployments/ bootstrap/ cli/src .devcontainer/Dockerfile`
  matches only the GCS prefix `minio/` in the backup jobspec and its comment.
  In `docs/`, every match is in a sentence about the move from MinIO.
- After the three applies, `terraform plan` in both roots reports no changes,
  and `terraform state list` in the applications root lists no `minio_*`
  address and nothing under `module.buckets`.
- `nomad job status minio` and `nomad job status backup-minio` report no such
  job, and `backup-s3`'s next run exits 0.
- `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- Terraform may still set up or refresh `provider "minio"` for resources it
  is only dropping from state. If `terraform plan` with the `removed` blocks,
  and with no `provider "minio"` block or `required_providers` entry, fails,
  then the provider has to stay configured while MinIO still runs, and
  step 1 splits into two applies (drop from state, then drop the provider)
  before step 2.
  Real, per `spike:minio-removal/1`: with the provider deleted, plan fails
  with "Provider aminueza/minio requires explicit configuration" and all
  nine resources stay in state. Cheap, per `spike:minio-removal/2`: a
  provider with static dummy values lets the `removed` blocks empty state
  with MinIO stopped and its Consul service and Vault key gone, and a second
  commit then drops the provider with a clean plan. Step 1 above is written
  that way, so step 2 does not wait on a running MinIO.
