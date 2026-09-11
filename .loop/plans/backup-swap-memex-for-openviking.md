---
epic = "backups"
priority = 30
summary = "Point the daily MinIO backup job at the `openviking` bucket instead of `memex`. The OV postgres database needs no change: `pg_dumpall` already covers it."
---
# Ticket: backup-swap-memex-for-openviking

## 1. Swap the daily MinIO backup from `memex` to `openviking`

Point the off-site MinIO backup at the bucket OpenViking actually writes to,
so it reaches GCS. Stop copying `memex` objects.

## 2. Size / Effort

**S.** One argument string in one jobspec, plus one drift test. Driven by the
test, not the edit.

## 3. Triggered by

Operator: "we need to stop backing up memex artifacts, and need to start
backing up the OV bucket and database."

## 4. Context

Two periodic batch jobs write off-site to one GCS bucket:

- `deployments/infrastructure/services/backup-minio.hcl:25` — `rclone sync
  minio:memex gcs:${gcs_bucket}/minio/memex/`. One bucket, hardcoded. Runs
  03:00 Europe/Amsterdam.
- `deployments/infrastructure/services/backup-postgres.hcl:29` — `pg_dumpall
  -h ${postgres_host}`, uploaded at
  `deployments/infrastructure/services/backup-postgres.hcl:56`. Runs 02:00.

Both are templated from `deployments/infrastructure/services.tf:701` and
`deployments/infrastructure/services.tf:713`. The GCS destination
`google_storage_bucket.backups`
(`deployments/infrastructure/storage.tf:6`) deletes objects at 180 days
(`deployments/infrastructure/storage.tf:13`).

What is wrong: `openviking` is a declared MinIO bucket
(`deployments/applications/storage.tf:63`) holding live OpenViking data, and
nothing copies it off-cluster. `memex` is still synced.

What is NOT wrong, contrary to the request's framing: the `openviking`
postgres database (`deployments/applications/database.tf:34`) is already
backed up. `pg_dumpall` dumps every database on the instance, and P3 below
shows the backup role is a superuser that can read this one.

## 5. Non-goals / out of scope

- No change to `deployments/infrastructure/services/backup-postgres.hcl` or
  its credentials. The database half of the request is already satisfied
  (P2, P3).
- No removal of the `memex` postgres database from the dump. `pg_dumpall` is
  all-or-nothing, and the operator asked to stop backing up memex
  *artifacts* (objects), not its relational data.
- No deletion of the existing `gcs:<bucket>/minio/memex/` prefix. Operator
  chose to let the 180-day lifecycle rule expire it.
- No widening of the job to sync more than one bucket. Operator chose
  `openviking` only.
- No new MinIO IAM policy or access key. P4 shows the existing root key
  already reads the bucket.
- No Terraform resource added, renamed, or destroyed.
- In `docs/gcs-backups.md`, only the facts that name `memex` as the synced
  bucket change (R6). Its postgres half, its Vault-path and credential
  sections, and its structure stay as they are. The one exception is the
  stale `No node constraint` claim at `docs/gcs-backups.md:72`, which
  `.claude/rules/pre-existing-issues.md` requires the agent that noticed it
  to fix.

## 6. Requirements & restrictions

- R1. The job syncs `minio:openviking` to `gcs:<bucket>/minio/openviking/`,
  and no longer names `memex`. Direct from the request. Delivered by the
  jobspec row in section 7.
- R2. The bucket the jobspec names must be a bucket that exists. Enforced by
  `test_minio_backup_syncs_a_declared_bucket` in section 8, which reads the
  declared bucket set at `deployments/applications/storage.tf:2`. `rclone
  sync` against a nonexistent bucket does not loudly fail a periodic batch
  job, so a typo here is a silent backup gap.
- R3. The jobspec is edited, not the Terraform around it. The file-layout
  rule (`.claude/rules/terraform-file-layout.md`) states a jobspec edit folds
  into `nomad_job.jobspec` and re-registers the job. That re-registration is
  the intended effect. Bounded by the two-row code surface in section 7.
- R4. The change ships with a test
  (`.claude/rules/python-testing.md`). Delivered by
  `cli/tests/test_backup_coverage.py` in sections 7 and 8.
- R5. Gates pass: `just pre_commit` (`.loop/config.json`), which runs
  `nomad fmt -recursive` over the changed `.hcl`
  (`.pre-commit-config.yaml:18`) and mypy strict over `cli/tests`
  (`.pre-commit-config.yaml:58`). Listed as a gate in section 8.
- R6. `docs/gcs-backups.md` stops describing a command the cluster no longer
  runs. It states the memex-specific sync at `docs/gcs-backups.md:68`, the
  GCS path tree at `docs/gcs-backups.md:105`, and the verify command at
  `docs/gcs-backups.md:137`. Delivered by the docs row in section 7.

## 7. Code surface

| File | Change |
|---|---|
| `deployments/infrastructure/services/backup-minio.hcl:25` | R1, R3: `memex` becomes `openviking` in both the rclone source and the GCS destination prefix. Only line touched. |
| `cli/tests/test_backup_coverage.py` | R2, R4: new file. Drift test that the bucket named in the jobspec is a declared bucket, and is `openviking`. Follows the parse-and-assert pattern of `cli/tests/commands/test_breakglass_runbook_facts.py:1`. |
| `docs/gcs-backups.md:5`, `:68`, `:72`, `:105`, `:137` | R6: the four places that name `memex` as the synced bucket become `openviking`, plus the stale `No node constraint` line at `:72`, which contradicts the jobspec's `radxa-dragon-q6a` constraint (`deployments/infrastructure/services/backup-minio.hcl:15`). |

Nothing else. `deployments/infrastructure/services.tf:713` already templates
the file and needs no edit; the jobspec is read at plan time, so the new bytes
reach Nomad with no Terraform change.

## 8. Tests & validation gates

Both tests live in `cli/tests/test_backup_coverage.py` (section 7). Each
carries a self-check, so a parser that finds nothing fails instead of passing
vacuously.

- `test_minio_backup_syncs_a_declared_bucket` (R2) — parse the `rclone sync
  minio:<bucket>` source out of
  `deployments/infrastructure/services/backup-minio.hcl`, parse the bucket
  keys out of `local.buckets` in `deployments/applications/storage.tf`,
  assert the first is in the second.
- `test_minio_backup_syncs_the_openviking_bucket` (R1, R4) — assert the
  parsed bucket is `openviking`, and that the GCS destination prefix names
  the same bucket, so source and destination cannot drift apart.

Gates, discovered from `.loop/config.json` and `.pre-commit-config.yaml`:

- `just pre_commit` (R5) — the configured gate. Covers `nomad fmt
  -recursive` on the `.hcl`, and ruff, ruff-format and mypy strict on the new
  test.
- `uv run --project cli pytest cli/tests/test_backup_coverage.py` — the new
  tests, run directly during implementation.
- `cd deployments/infrastructure && just plan` — expected to show
  `1 to change` (`nomad_job.backup_minio`, its `jobspec` attribute) and
  nothing else. Not a pre-commit hook; run it by hand and read the plan. This
  is what settles P5.

## 9. Risk assessment

Blast radius: one periodic batch job. Reversible by reverting one line.

Failure modes, likeliest first:

1. The swap lands but `rclone sync` cannot read `openviking` — refuted by P4,
   which listed the bucket with the job's own credentials.
2. Terraform reports more than `nomad_job.backup_minio` changing. Would mean
   the edit touched something outside the intended line. Caught by reading the
   plan (section 8).
3. Someone later reads "we stopped backing up memex" as also covering its
   database. It does not. Section 5 records this, and the dump still contains
   the `memex` database.

Not a risk: data loss. Nothing is deleted; the `memex` prefix in GCS keeps
its existing contents until the 180-day rule expires them.

## 10. Subtickets

None. The single edit (R1, R3) and its test (R2, R4) fit one iteration, gated
by R5.

## 11. Open questions

None outstanding. Two forks were put to the operator before this ticket was
written and both are settled, recorded in section 5:

- Scope of the sync: `openviking` only, not a widened multi-bucket job.
- Existing `minio/memex/` data in GCS: left to expire under the 180-day
  lifecycle rule rather than deleted now.

## Premises / assumptions

- **P1.** The MinIO backup job today syncs exactly one bucket, `memex`.
  Anchor: `deployments/infrastructure/services/backup-minio.hcl:25`, the
  `args` string.
- **P2.** The `openviking` database exists on the same postgres instance
  `deployments/infrastructure/services/backup-postgres.hcl:29` dumps, so
  `pg_dumpall` already covers it. probe: run against `192.168.2.30` with the
  job's own credentials read from
  `secret/default/backup-postgres/postgres`:

  ```
  $ psycopg.connect(host="192.168.2.30", user=$PGUSER, dbname="postgres")
    .execute("select datname from pg_database where not datistemplate order by 1")
  POSTGRES DBS: ['bifrost', 'ducklake', 'localstack', 'memex', 'openviking',
                 'phoenix', 'postgres']
  ```

- **P3.** The backup role can actually read that database, so `pg_dumpall`
  does not silently skip it. probe: run against `192.168.2.30` on the same
  connection as P2:

  ```
  $ select rolname, rolsuper from pg_roles where rolname = current_user
  BACKUP ROLE: ('localstack', True)
  $ select has_database_privilege(current_user, 'openviking', 'CONNECT')
  CAN CONNECT openviking: True
  $ select count(*) from information_schema.tables
      where table_schema not in ('pg_catalog','information_schema')  -- on openviking
  OPENVIKING USER TABLES VISIBLE: 18
  ```

- **P4.** The `openviking` bucket exists on MinIO and the backup job's
  credentials can list it, so no new IAM policy or access key is needed.
  probe: run against `192.168.2.29:9000` with the job's own credentials read
  from `secret/default/backup-minio/minio`:

  ```
  $ boto3.client("s3", endpoint_url="http://192.168.2.29:9000").list_buckets()
  MINIO BUCKETS: ['datalake', 'loki', 'memex', 'mlflow-artifacts', 'models',
                  'openviking', 'registry', 'tempo']
  $ list_objects_v2(Bucket="openviking", MaxKeys=1)
    openviking: has_objects=True
  ```

- **P5.** Editing the jobspec re-registers the Nomad job with no other
  Terraform churn, because `templatefile` folds the file into
  `nomad_job.jobspec`. Cited source: `.claude/rules/terraform-file-layout.md`
  ("Editing a comment there re-registers the job"), anchored at
  `deployments/infrastructure/services.tf:713`. UNCERTAIN until `just plan`
  confirms `1 to change`; section 8 makes that a gate.
- **P6.** Stale objects under `gcs:<bucket>/minio/memex/` expire on their own.
  Anchor: `deployments/infrastructure/storage.tf:13`, `age = 180` with a
  `Delete` action. Not probed against GCS; read from the resource that
  manages the rule.
