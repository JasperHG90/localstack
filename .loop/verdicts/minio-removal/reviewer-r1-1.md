---
type: verdict
title: 'Verdict: minio-removal reviewer round 1'
description: 'reviewer verdict for round 1 of minio-removal: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T09:11:12+00:00'
slug: minio-removal
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. MinIO is gone from the code, from the
applications state and from Nomad. The backup job runs as `backup-s3` from
`default/backup-s3/*`, ov-dash is back, and the gates are green on a stamp I
ran myself. The plan and eval amendments are sound: `mc` is an S3 client
pointed at SeaweedFS, and each name the r1 allowlist keeps has a stated reason
that does not depend on MinIO running. Nothing blocks.

## Checked

- Gates: `loopctl gate stamp` from the worktree passed `pre_commit`,
  `cli_tests` and eval row r1 (stamp
  64c1255701e334a4582c54eb2b4fb9d13b3c1b50264c8d1b76affd2617499c71). The
  pinned `kmctl check` (v0.10.0) reports all checks passed.
- Diff: I read the staged change against HEAD 9fe1ebe. `git diff --cached
  main` also shows main's later harness commits (justfile, apm, .opencode),
  which do not belong to this ticket. I read every code, test and Terraform
  hunk in full, and the docs that carry claims: the three new how-tos, the
  workload-identity explanation, gcs-backups, monitoring, edge-routes,
  run-a-backup-job-on-demand, ADR 0018, `components/minio.md`, the manifesto
  and the summary.
- r1 (command): `cli/tests/test_no_minio.py` walks `deployments/`,
  `bootstrap/`, `cli/src` and the Dockerfile. It fails on any line that names
  MinIO (case-insensitive) once a per-file allowlist pattern is removed. The
  allowlist is narrow: `minio/` only in backup-s3.hcl and restore-s3.hcl,
  `minio_data` only in services.tf, `minio-go` only in tempo.hcl, and the mc
  URL plus its comment only in the Dockerfile. A second test proves the scan
  reads backup-s3.hcl, so an empty walk cannot pass. It checks the row's
  fails_when. My own grep finds only the allowed names, and the gitignored
  applications lock file no longer names minio.
- r2 (judgment): I checked it live myself rather than trusting the report.
  `terraform state list` in applications has 0 `minio`/`module.buckets`
  addresses. `terraform plan -lock=false` reports "No changes" in
  applications. In infrastructure it lists only the 15
  `null_resource.firewall` replacements that the `always_run` trigger forces
  on every plan. The removed blocks used `destroy = false`, so no bucket or
  object was deleted, and spike 4 records the evidence.
- r3 (judgment): `nomad job status minio` and `backup-minio` return 404.
  `backup-s3` is a registered periodic job with its next launch at 03:00, and
  spike 4 records the forced run's exit 0. In Vault, `default/backup-s3/gcs`
  and `default/backup-s3/seaweedfs` are live. `default/minio/localstack` and
  all of `default/backup-minio/*` have no metadata left, so they were purged.
- r4 (judgment): the three MinIO how-tos are replaced by SeaweedFS ones. They
  match the code (`local.seaweedfs_keyless_jobs`, tempo's three env vars, the
  `#keyless-seaweedfs-access` anchor) and keep the how-to skeleton.
  `workload-identity.md` describes SeaweedFS, and MinIO appears only in a
  "Before SeaweedFS" paragraph. `components/minio.md` is `status:
  deprecated` with a "Superseded by SeaweedFS" lead, because the bundle has no
  superseded status. ADR 0018 records the removal and the rejected
  volume-destroy. No docs page tells a reader to use MinIO, and no link
  points at a deleted page.
- Correctness spots: `seaweedfs_buckets = local.buckets` matches the old
  drop-filter result, since memex and mlflow-artifacts left the catalog.
  `backup_s3` reads the renamed paths. The comment edit inside `rules_hcl` in
  `machine_roles.tf` rewrites the deploy policy, but that apply already ran
  and the plan is clean. The memex staging note points at a real SeaweedFS
  port and Consul lookup.

## Findings

None.

## Notes

- The plan says `cli/tests/test_health_rules.py` should follow the rename,
  but it still parametrizes `backup-minio`. That job name comes from a
  captured `/v1/jobs/statuses` fixture, which also still lists `promtail`.
  Renaming the job inside a recorded capture would falsify it, so leaving it
  is right. The plan line was too broad.
- The plan's Outcome bullet still lists only the backup prefix and mc as the
  names left. The amended r1 row also allows restore-s3, `minio_data` and
  `minio-go`. The row is the contract and it is right, so the plan text is
  just behind.
- Soft-deleted versions remain in Vault at `default/<job>/minio` (for
  example `default/loki/minio`), and the MinIO users still exist inside
  `minio_data`. Nothing serves them while MinIO is stopped.
  `minio-volume-destroy` is the natural place to purge both.
