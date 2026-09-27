---
type: component
title: GCS backups
description: "Two periodic jobs on radxa copy Postgres (pg_dumpall) and one MinIO bucket (openviking) to a GCS bucket, each reading copies of the root credential and the same GCS key. A drift test pins the bucket name and the reference page's facts, but no gate runs it, no alert watches the jobs, and no restore has been tried."
tags: [backup, gcs, postgres, minio, nomad, vault, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: backup-postgres-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/backup-postgres.hcl
  - id: backup-minio-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/backup-minio.hcl
  - id: infra-storage
    resource: git:3ec5d1e:deployments/infrastructure/storage.tf
  - id: infra-secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: backup-coverage-test
    resource: git:3ec5d1e:cli/tests/test_backup_coverage.py
  - id: move-off-firebat-commit
    resource: git:4b0af46
  - id: backup-swap-memex-for-openviking
    resource: loop:backup-swap-memex-for-openviking
  - id: gcs-backups-doc-to-runbook
    resource: loop:gcs-backups-doc-to-runbook
  - id: R8-rollout-postgres-root-consumers
    resource: loop:R8-rollout-postgres-root-consumers
---

# GCS backups

What the jobs run, their images, schedules and GCS layout are in
`docs/reference/gcs-backups.md`. Why each job reads its own copy of a
credential is `docs/explanation/backup-job-credentials.md`. This page covers
how the parts connect and what the design does not protect against.

## The pieces

Everything is in the infrastructure root, one file per subsystem:

- `storage.tf`: the GCS bucket (`var.gcs_backup_bucket`, 180-day delete
  rule), service account `localstack-backup`, `roles/storage.objectAdmin` on
  the bucket, and `google_service_account_key.backup`.
- `secrets.tf`: four KV entries under the jobs' own prefixes.
  `default/backup-postgres/postgres` copies `random_password.postgres_root`,
  `default/backup-minio/minio` copies `random_password.minio_secret_key`, and
  both `.../gcs` entries hold the same decoded key JSON.
- `services.tf`: `nomad_job.backup_postgres` and `nomad_job.backup_minio`,
  with the Postgres and MinIO node addresses passed in as literals.
- `deployments/infrastructure/services/backup-postgres.hcl` and
  `deployments/infrastructure/services/backup-minio.hcl`.

The Google provider authenticates with the operator's ADC, so an apply needs a
`gcloud` login on top of the usual Vault session.

## Credentials are copies of root

The copies exist because `nomad-workloads` lets a job read only its own
prefix. They scope the PATH, not the privilege: `backup-postgres` logs in as
the Postgres superuser `localstack`, and `backup-minio` holds the MinIO root
key. Both copies follow their source in the same apply, because they reference
the same `random_password`. For Postgres that is not enough, since the server
keeps its first password (see [Postgres](/components/postgres.md)).

R8 owns moving `backup-postgres` off root. Its open question is whether
`pg_dumpall` works at all without superuser, since it dumps roles and their
passwords. `backup-minio` could use a claim-mode policy named `backup-minio`
([MinIO](/components/minio.md)). No ticket covers that.

The GCS key is a long-lived JSON key held in Terraform state and in two KV
entries. Rotating it means replacing `google_service_account_key.backup`.

## What is and is not covered

- `pg_dumpall` copies every database on the server, so a new database is
  covered with no edit. That is how `openviking` got covered.
- `rclone sync` copies ONE bucket, `openviking`. It was `memex` until
  backup-swap-memex-for-openviking swapped it. Images, ModelKits, logs, traces
  and the `datalake`, `models` and `mlflow-artifacts` buckets have no off-site
  copy.
- No other host volume is copied: NATS JetStream, OpenViking's workspace,
  hermes, embark, Prometheus, Grafana and the acme state included. Nor is
  Vault's Consul storage. See [Host volumes](/components/host-volumes.md).

## The enforcer, and its reach

`cli/tests/test_backup_coverage.py` pins the MinIO bucket in
`backup-minio.hcl` to a key of `local.buckets` in
`deployments/applications/storage.tf`, and pins the GCS prefix to the same
name, because `rclone sync` against a missing bucket does not fail loudly.
It also pins the reference page's provider version, node constraints, per-task
CPU and memory, crons and images to the sources. Each parser fails if it
finds nothing, and the doc checks bind figures to their task: a reviewer
swapped the `pgdump` and `upload` figures and a section-wide check stayed
green, and that pair is the one that had drifted before.

`just pre_commit`, which is also the loop's gate, runs ruff and mypy over
`cli/` but not pytest. The tests run only from `cli/` (`just test` or
`uv run pytest`). Nothing checks the Vault paths, the GCS bucket, the host
literals, or that a backup can be read back.

## Traps

- **A stuck child blocks every later run.** With `prohibit_overlap = true`, a
  child that cannot place stays pending and every later night is skipped.
  `backup-postgres` was pinned to firebat, where Postgres had taken the CPU,
  and no backup ran for about two months (4b0af46). Both jobs now run on
  radxa-dragon-q6a and reach the services over the LAN. Keep them off the
  nodes that host what they copy.
- **Failures are invisible.** With the operator's token, the Nomad ACL
  returned 403 on the query that lists a periodic job's children
  (gcs-backups-doc-to-runbook), and no alert rule watches either job.
- **A failed dump uploads as success.** The `pgdump` command is
  `pg_dumpall ... | gzip > file` under `/bin/sh -c` with no `pipefail`, so the
  task's exit code is gzip's. A dump that dies halfway leaves a truncated
  `.sql.gz`, the prestart task succeeds, and `upload` copies it.
- **The 180-day rule and the mirror.** The lifecycle rule deletes objects by
  age, and `minio/openviking/` is a mirror, not a series. An object older than
  180 days in GCS is deleted there and re-uploaded by the next sync, so it has
  no off-site copy for up to a day. The reference page calls the rule "a
  safety net for orphaned objects", but `rclone sync` already removes those.
- **Floating image.** Both jobs run `rclone/rclone:latest`.
- **Staging is on radxa.** The dump is written to the allocation directory on
  radxa before upload, so a very large database needs that much free disk
  there.
- **Restore is unproven.** No read-back has been recorded.
