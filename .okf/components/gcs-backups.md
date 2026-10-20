---
type: component
title: GCS backups
description: "Two periodic jobs on radxa copy Postgres (pg_dumpall) and the four durable MinIO buckets (openviking, registry, models, datalake) to a GCS bucket, each reading copies of the root credential and the same GCS key. A drift test pins the bucket set and the reference page's facts and runs in the loop's pytest gate, not in pre-commit. No alert watches the jobs, and no restore has been tried."
tags: [backup, gcs, postgres, minio, nomad, vault, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: backup-postgres-jobspec
    resource: deployments/infrastructure/services/backup-postgres.hcl
  - id: backup-minio-jobspec
    resource: deployments/infrastructure/services/backup-minio.hcl
  - id: infra-storage
    resource: deployments/infrastructure/storage.tf
  - id: infra-secrets
    resource: deployments/infrastructure/secrets.tf
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: backup-coverage-test
    resource: cli/tests/test_backup_coverage.py
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

R8 planned moving `backup-postgres` off root, and was still a stub when
`5b2ed1b` reset the loop. Its open question is whether `pg_dumpall` works at
all without superuser, since it dumps roles and their passwords. `backup-minio` could use a claim-mode policy named `backup-minio`
([MinIO](/components/minio.md)). No ticket covers that.

The GCS key is a long-lived JSON key held in Terraform state and in two KV
entries. Rotating it means replacing `google_service_account_key.backup`.

## What is and is not covered

- `pg_dumpall` copies every database on the server, so a new database is
  covered with no edit. That is how `openviking` got covered.
- `rclone sync` copies four buckets: `openviking`, `registry`, `models` and
  `datalake` (backup-durable-buckets, the first step of the SeaweedFS
  migration, which restores from this copy). Each sync runs even if an
  earlier one failed, and any failure fails the task. Before this change the
  sync ran with no flags, which drops OpenViking's zero-byte directory keys,
  so copies made before 2026-10-20 have no empty directories. The first
  run with the marker flags (2026-10-20) restored them, and a per-key
  comparison found every MinIO file and directory in GCS
  (`spike:backup-durable-buckets/3`). Logs and traces
  (`loki`, `tempo`, 30 days each) and `memex` and `mlflow-artifacts`, which
  the migration drops, have no off-site copy.
- No other host volume is copied: NATS JetStream, OpenViking's workspace,
  hermes, embark, Prometheus, Grafana and the acme state included. Nor is
  Vault's Consul storage. See [Host volumes](/components/host-volumes.md).

## The enforcer, and its reach

`cli/tests/test_backup_coverage.py` pins the set of MinIO buckets in
`backup-minio.hcl` to the four durable ones, each to a key of
`local.buckets` in `deployments/applications/storage.tf`, pins each GCS
prefix to the same name, and checks that every sync records its failure,
because `rclone sync` against a missing bucket does not fail loudly.
It also pins the reference page's provider version, node constraints, per-task
CPU and memory, crons and images to the sources. Each parser fails if it
finds nothing, and the doc checks bind figures to their task: a reviewer
swapped the `pgdump` and `upload` figures and a section-wide check stayed
green, and that pair is the one that had drifted before.

`just pre_commit` runs ruff and mypy over `cli/` but not pytest, so a plain
commit does not run this test. The loop runs it: since `5b2ed1b` its gates in
`.loop/config.toml` are `just pre_commit` and `uv run --directory cli pytest`,
so every ticket's stamp runs it. Nothing checks the Vault paths, the GCS
bucket, the host literals, or that a backup can be read back.

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
  age, and each `minio/<bucket>/` prefix is a mirror, not a series. An object older than
  180 days in GCS is deleted there and re-uploaded by the next sync, so it has
  no off-site copy for up to a day.
- **Floating image.** Both jobs run `rclone/rclone:latest`.
- **Staging is on radxa.** The dump is written to the allocation directory on
  radxa before upload, so a very large database needs that much free disk
  there.
- **Directory markers differ by bucket.** A flagged sync onto an existing
  copy writes markers only for empty directories (93 for `openviking`), while
  a first flagged copy writes one per directory: `registry` has 725 markers
  in GCS and no directory keys in MinIO. A restore with
  `--s3-directory-markers` creates all 725 as zero-byte `dir/` keys
  (`spike:backup-durable-buckets/3`).
- **Names with LF or CR.** rclone's GCS encoding stores them as U+240A and
  U+240D, so a listing compared by hand shows them as mismatches. rclone
  decodes them back on restore.
- **Restore is unproven.** No read-back has been recorded.

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- commit `4b0af46`
- loop ticket `backup-durable-buckets` (its plan, spikes and verdicts are under `.loop/`)
- loop ticket `backup-swap-memex-for-openviking` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `gcs-backups-doc-to-runbook` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R8-rollout-postgres-root-consumers` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
