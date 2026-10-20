---
type: verdict
title: 'Verdict: seaweedfs-cutover reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-cutover: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T08:30:43+00:00'
slug: seaweedfs-cutover
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. The backup job reads SeaweedFS with the read-only `backup` key at `default/backup-minio/seaweedfs` and keeps the `minio/<bucket>/` GCS prefixes. The `s3` tag, the `s3.lab` backend, the dash tile and the devcontainer alias all point at SeaweedFS. `minio.lab` stays on MinIO. The tests pin each of these, and the live evidence covers r3 and r4. Nothing blocks.

## Checked

- Gates, run by me from the worktree with `loopctl gate stamp`: pass pre_commit, pass cli_tests, pass r1, pass r2, "stamp green: 92314f7a232a53e9953f806b9bff59441217b852592b557a7a61d5f934fe1131". `kmctl check` (uvx, v0.10.0) reports "all checks passed" and leaves the tree unchanged.
- Code read in full: backup-minio.hcl, services.tf (`nomad_job.backup_minio`), haproxy.hcl, minio.hcl, seaweedfs.hcl, tiles.json, bootstrap.sh, .env.example, the CLI comment changes, and every changed test and fixture. The secret path the job templates matches `vault_kv_secret_v2.backup_seaweedfs_credentials` in deployments/applications/secrets.tf. It sits under the job's own `default/backup-minio/*` path, which the workloads policy allows. The `.env.example` access key `admin` matches `default/seaweedfs/admin`. The applications root's aws provider sets its keys explicitly, so the devcontainer's `AWS_*` variables cannot leak into Terraform. `git grep 192.168.2.29:9000` finds it only in prometheus.hcl among the jobspecs. memex.hcl's `${minio_host}:9000` belongs to a job that services.tf has commented out.
- r1: test_backup_coverage.py fails if any sync line still reads `minio:`, because the transfer count no longer matches the `seaweedfs:` lines. It also fails if a bucket is missing, if a destination prefix differs from its source, or if a marker flag is dropped. The new test pins `provider = SeaweedFS`, the endpoint on 8333 and the key path in services.tf. Each part of fails_when is covered.
- r2: test_s3_cutover.py pins `s3_1 192.168.2.29:8333`, keeps `minio.lab` on 9001, rejects a `minio` tile key, pins the `s3` alias and `.env.example`, and scans every `.hcl` for MinIO's address. test_seaweedfs_jobspec.py asserts that `s3` is on seaweedfs and not on minio. The CLI's tag lookup is covered by test_services.py and test_read_commands.py in the cli_tests gate.
- r3 (judgment, spike 4): the per-key listing ran before the switch. It found no missing files in any bucket. The 725 registry keys missing on SeaweedFS are all zero-byte `dir/` markers, deleted on purpose (spike seaweedfs-cutover-registry/2). The 5 openviking keys that differ all have SeaweedFS modtimes after the 07:02:45 restore, and OpenViking is that bucket's only writer. models and datalake are empty. Met in substance (see Notes).
- r4 (judgment, spike 5, plus my own read-only checks): the backup alloc d12af9d8 exited 0. Afterwards GCS matched SeaweedFS file for file in all four buckets. I confirmed live that the Consul catalog has `seaweedfs: [s3, http]` and `minio: [http]`, and that `s3.lab` answers `server: SeaweedFS 30GB 4.48`. The MinIO alloc 4cf10997 still runs at version 14, so the job was updated in place without a restart. `nomad job history dash` shows the last applications-root submit at 08:12:41 UTC, before the first MinIO count at 08:12:58. The two counts, 08:12:58 and 08:24:46, are identical and more than 10 minutes apart. Docs and `.env.example` are as the row requires.
- Consistency: docs/reference/gcs-backups.md, edge-routes.md, cli-read-commands.md, the backup how-to, the two explanation pages and the .okf component and node pages match the code. The comment in services.tf about cross-root apply order is accurate.

## Findings

None.

## Notes

- r3 departs from the plan's wording. The check was a boto3 and GCS listing that compares keys and sizes, not `rclone check --one-way` with hashes. It recorded counts and a coded modtime test rather than named lists. The key comparison catches the case that matters, a GCS object about to be deleted. Size-only matching could miss a same-size rewrite, but the sync would overwrite that object with the newer SeaweedFS copy anyway. The GCS state has moved on since, so there is nothing left to redo.
- Three how-tos still teach keyless MinIO access: give-a-job-keyless-minio-access, give-an-aws-sdk-go-service-keyless-minio-access and exchange-a-workload-jwt-for-minio-credentials. Each says no job uses the MinIO form today. The minio-removal plan replaces them by name, so I left them to that ticket.
- `backup_minio_s3_credentials` is still written and nothing reads it. The docs say so, and minio-removal deletes it.
