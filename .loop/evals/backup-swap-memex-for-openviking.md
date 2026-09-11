eval: backup-swap-memex-for-openviking

**Definition of Done:** the nightly off-site MinIO backup copies the
`openviking` bucket and no longer copies `memex`, the bucket it names is
provably a real bucket, and `docs/gcs-backups.md` describes the job the
cluster actually runs.

| Behavior | Input | Expected | Fails-when | Scorer | Threshold |
|---|---|---|---|---|---|
| The nightly MinIO backup copies the OpenViking bucket off-site | `deployments/infrastructure/services/backup-minio.hcl`, the `args` string of task `sync` | The rclone source reads `minio:openviking` and the GCS destination reads `gcs:<bucket>/minio/openviking/`. Neither names `memex`. | The line still reads `minio:memex`, or only the source was swapped and the destination prefix still says `memex`. | deterministic: `test_minio_backup_syncs_the_openviking_bucket` in `cli/tests/test_backup_coverage.py` | 100% |
| The bucket the backup job names is a bucket that exists | The bucket parsed from the jobspec, against the keys of `local.buckets` in `deployments/applications/storage.tf` | The parsed name is a member of the declared bucket set. | The jobspec names a bucket absent from `local.buckets` (for example a typo, `openvikng`), which `rclone sync` would not loudly fail on. Also fails if either parser returns nothing, so a broken parser cannot pass vacuously. | deterministic: `test_minio_backup_syncs_a_declared_bucket` in `cli/tests/test_backup_coverage.py` | 100% |
| Backups keep landing in GCS under a path that matches the bucket | The rclone source bucket and the GCS destination prefix, parsed separately from the same `args` string | Both name the same bucket, so a future swap cannot move the source while leaving the destination pointing at the old prefix. | Source says `openviking` and destination says `memex` (or any other mismatched pair). | deterministic: `test_minio_backup_syncs_the_openviking_bucket` in `cli/tests/test_backup_coverage.py` | 100% |
| The backup runbook describes the job the cluster actually runs | `docs/gcs-backups.md`, lines 5, 68, 72, 105 and 137 | The sync command, the GCS path tree, and the `gsutil ls` verify command all name `openviking`. The stale `No node constraint` claim at `:72` matches the jobspec's `radxa-dragon-q6a` constraint. | The doc still tells a reader to run `gsutil ls gs://<bucket>/minio/memex/`, or still claims the job has no node constraint. | human with rubric: read the five lines against `backup-minio.hcl` | 100% |
| Swapping the bucket re-registers one job and disturbs nothing else | `cd deployments/infrastructure && just plan` | The plan reports `1 to change` for `nomad_job.backup_minio`, its `jobspec` attribute, and adds or destroys nothing. Any other listed resource is accounted for before the change is called clean. | The plan lists a resource beyond `nomad_job.backup_minio` that the operator cannot account for, or reports an add or a destroy. | human with rubric: operator reads the plan output | 100% |

Notes:

- Row 5 cannot be scored by a test: `terraform plan` takes a state lock
  against live infrastructure, so no unattended scorer may run it. The
  operator runs it and reads the output.
- Rows 1 and 3 share one test because they are two claims about the same
  parsed line; the test asserts each separately.
- Not scored here, deliberately: the `openviking` postgres database. It was
  already covered by `pg_dumpall` before this ticket (plan premises P2 and
  P3, re-probed by the plan reviewer against the job's own image), so a row
  asserting it would green without this change doing anything.


signed-off-by: JasperHG90 2026-09-11
