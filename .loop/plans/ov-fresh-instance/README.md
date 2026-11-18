---
type: plan
title: 'Plan: ov-fresh-instance'
description: Point OpenViking at a new SeaweedFS bucket, a new Postgres schema and a new workspace volume, bootstrapped with one account lab and one user jasper, and leave the old bucket, schema and volume untouched as a read-only backup.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T13:54:01+00:00'
slug: ov-fresh-instance
epic: ov-reset
depends_on: []
priority: 2
---

# ov-fresh-instance

Relayed from: none

## Intent

Operator, 2026-10-20: start OpenViking over against a new bucket. One account,
`lab`, and one user, `jasper`, shared by the operator, Hermes and CI. The old
bucket and the old vector store stay as they are, as a read-only backup, until
the operator says delete. Deleting them is not this ticket.

Today OpenViking stores blobs in SeaweedFS bucket `openviking`, vectors in
schema `openviking` of Postgres database `openviking`, and working state
(the queue database under _system/queue, RAGFS scratch) in host volume
`openviking_data`, mounted at `/app/.openviking`
(`deployments/applications/services/openviking/ov.conf.json`,
`deployments/applications/services/openviking.hcl`). The old bucket holds
account `lab` plus the per-person accounts `jasper` and `veerle` that OV2
created, and users `jasper`, `hermes`, `veerle` and `default`
(`deployments/infrastructure/oidc.tf` records `lab` at 2920 objects).

### Who reaches OpenViking, and as whom

Read from the code. Every caller already resolves to `lab`/`jasper` except one:

| Caller | Where set | Identity |
|---|---|---|
| operator CLI, ov-dash sign-in | `var.vault_operator_ov_identity`, `deployments/infrastructure/variables.tf` | `lab`/`jasper` |
| hermes, leo-consumer | `var.vault_openviking_workloads`, same file | `lab`/`jasper` |
| ov-ext reflection | `OV_REFLECT_ACCOUNT_ID`/`OV_REFLECT_USER_ID` in `deployments/applications/services/openviking.hcl` | `lab`/`jasper` |
| CI sync (draft ticket `ci-openviking-sync`, not built) | its plan | `lab`/`jasper` |
| veerle | `var.vault_openviking_consumers` | `lab`/`veerle` |

Hermes reaches OpenViking through its sidecar with the `openviking-hermes`
identity token and `openviking_account = "lab"`
(`deployments/applications/services.tf`). No openfang workload maps to
OpenViking. The per-person API keys under `default/openviking-users/` in
`deployments/applications/secrets.tf` still name accounts `jasper` and
`veerle`, but nothing reads them under `auth_mode: oidc`
(`docs/explanation/openviking-identity.md`). This ticket leaves them alone.

### What changes

New names: bucket `openviking-v2`, schema `openviking_v2`, host volume
`openviking_data_v2`. The operator may rename them before build.

- **`deployments/applications/storage.tf`**: add bucket `openviking-v2` to
  `local.buckets` and move the existing `openviking` writer user onto it. The
  `openviking` bucket keeps its entry with `writers = []`. The IAM user and its
  access key keep their addresses, so `default/openviking/seaweedfs` does not
  change, while the key loses all access to the old bucket. That is what keeps
  the old bucket read-only in fact, not by convention. Add `openviking-v2` to
  `local.seaweedfs_durable_buckets` and keep `openviking` there, so the backup
  user can read both and the restore user can write both.
- **`deployments/applications/services/openviking/ov.conf.json`**:
  `storage.agfs.s3.bucket` to `openviking-v2`,
  `storage.vectordb.custom_params.schema` to `openviking_v2`.
- **`deployments/applications/services/openviking.hcl`**:
  `OV_REFLECT_DELTAS_SCHEMA` to `openviking_v2`, and the `openviking_data`
  volume's `source` to `openviking_data_v2`. A fresh volume, so the old queue,
  with jobs that name old URIs, cannot replay into the new bucket, and the old
  workspace stays as part of the backup.
- **`deployments/infrastructure/services.tf`**: add
  `nomad_dynamic_host_volume.openviking_data_v2`, same shape and node as
  `openviking_data`. The old volume stays.
- **`deployments/infrastructure/services/backup-s3.hcl`**: one more checked
  `rclone sync` line, `seaweedfs:openviking-v2` to
  `gcs:<bucket>/minio/openviking-v2/`, with the same marker flags. It must not
  sync into `minio/openviking/`: `rclone sync` deletes at the destination, so
  the new bucket would erase the old one's GCS copy.
  **`deployments/infrastructure/services/restore-s3.hcl`**: add
  `openviking-v2` to the durable-bucket `case`.
- **`deployments/infrastructure/variables.tf`**: remove veerle's entry from
  `var.vault_openviking_consumers`, so her OpenViking access goes (operator's
  decision: one user, `lab`/`jasper`). Nothing else in Vault changes.
- **Bootstrap**: none for the account. Under OIDC a token with
  `ov_account=lab`, `ov_user=jasper` works on an empty bucket with no Admin
  API call (spike:ov-fresh-instance/2). The schema `openviking_v2` must exist
  before the first boot: ov-ext opens its delta store in `install()`, before
  the adapter creates the schema, so otherwise change capture stays off until
  a restart (spike:ov-fresh-instance/1). Create it as the `openviking` role
  (`CREATE SCHEMA IF NOT EXISTS openviking_v2`) in the cutover, with the
  command written in the README beside the image
  (`deployments/applications/services/openviking/README.md`), not a
  Terraform provisioner (`deployments/applications/services.tf` explains why
  the last one was removed).
- **Tests**: the durable-bucket sets in `cli/tests/test_seaweedfs_buckets.py`,
  `cli/tests/test_backup_coverage.py` and `cli/tests/test_restore_s3.py` gain
  `openviking-v2`, and a test asserts no sync line writes `openviking-v2` into
  another bucket's GCS prefix.
- **Knowledge**: a decision record (`kmctl new decision`) for starting fresh
  with the old store kept read-only and the key moved off it. Updates to
  `.okf/components/openviking-service.md`,
  `.okf/components/openviking-database.md`, `.okf/components/gcs-backups.md`,
  `.okf/components/host-volumes.md`, `docs/reference/openviking.md` and
  `.okf/summary.md`.

### Cutover order

First stop the `openviking` job, so nothing (the hourly reflection sweep,
Hermes, leo-consumer) writes to the old store. Then record a baseline of the
old store. For the bucket, an
`rclone lsf -R --format pst` listing plus `rclone md5sum` of `openviking`, as
the backup key. For the schema, per-table row counts and
`n_tup_ins + n_tup_upd + n_tup_del` from `pg_stat_user_tables` for schema
`openviking`, and `pg_dump --schema=openviking` hashed. Then apply
infrastructure, create schema `openviking_v2`, apply
applications. Restart Hermes so it opens a new
session rather than committing to one the new instance has never seen. The
nightly backup fails between the two applies, because the bucket does not
exist yet, so apply both in one sitting.

### Outcome

OpenViking runs on `openviking-v2` and schema `openviking_v2` with a fresh
workspace, and `/ready` answers 200. A listing of `openviking-v2` holds only
`backend_meta.json`, the preset `default` tree that `OpenVikingService` writes
on every start (openviking/service/core.py:367-369; spike:ov-fresh-instance/2)
and, once written to, `lab/` content. No `_system/` accounts or users files
exist under OIDC, and no account other than `lab` holds content. A search as `lab`/`jasper` returns zero results. The
operator's CLI token (`vault read identity/oidc/token/openviking`) and Hermes's
token both resolve to `lab`/`jasper` (`scripts/ov_identity_probe.py`), and
Hermes's `viking_search` tool answers through its sidecar. The old bucket's
listing and checksums, the old schema's dump hash and its tuple counters match
the baseline exactly. The next `backup-s3` run copies both buckets to their own
GCS prefixes. `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- Bootstrap on an empty bucket under OIDC. Settled by
  spike:ov-fresh-instance/3 (spike:ov-fresh-instance/2 ran the same setup
  against the earlier "only lab/jasper" outcome, which the preset `default`
  tree failed): on image v0.4.17.1-9 with `auth_mode: oidc`, an
  empty SeaweedFS bucket and empty schema, a token with `ov_account=lab`,
  `ov_user=jasper` passed ls, mkdir, write, read, find and search on the
  first try with no Admin API call. No `_system/` accounts or users files are
  written under OIDC. Startup always writes the preset `default` account and
  user tree, so the outcome allows it.
- A second schema in the same database. Settled by spike:ov-fresh-instance/1:
  the ov-postgres adapter created `openviking_v2` and its tables; schema
  `openviking`'s tuple counters and dump hash were unchanged after a boot,
  writes, a search and a reflection sweep on `openviking_v2`, and nothing
  new appeared in `public`. The schema must exist before ov-ext's first boot
  (see Bootstrap).
- Moving the `openviking` storage user's policy to `openviking-v2` on
  SeaweedFS (plan-review round 1, finding p1). Terraform replaces the
  policy because its name includes the bucket. Settled by
  spike:ov-fresh-instance/4: on SeaweedFS 4.48 with the service's IAM flags
  the move applied, the access key id and secret were unchanged, the next
  plan was clean, and the key was denied put, get, list and delete on
  `openviking` while it kept full access to `openviking-v2`; the backup key
  read both. All checks held again after a restart.
