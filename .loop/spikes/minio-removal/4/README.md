---
type: spike
title: Spike minio-removal/4
description: after the applies in plan order, is the applications state free of MinIO, do both roots plan clean apart from the always-run firewall rules, are minio and backup-minio gone, does backup-s3 run, and is ov-dash back?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:53:30+00:00'
slug: minio-removal
n: 4
outcome_written: true
---

# Spike minio-removal/4

after the applies in plan order, is the applications state free of MinIO, do both roots plan clean apart from the always-run firewall rules, are minio and backup-minio gone, does backup-s3 run, and is ov-dash back?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/rm-verify/verify.sh
```

## Outcome

Yes. The sequence on 2026-10-20 (UTC) followed the plan's order:

- Step 1A (applications root): `removed { lifecycle { destroy = false } }` for every `minio_*` resource and `module.buckets`, with a provider given static dummy values. 58 resources were forgotten and none destroyed. The apply added `default/backup-s3/seaweedfs` and destroyed the 15 MinIO key entries in Vault. Afterwards state held 0 MinIO addresses.
- Step 1B: the removed blocks, the provider and its `required_providers` entry were deleted, `terraform init` re-ran, and the plan reported no changes.
- Step 2, 08:39 (infrastructure root): removed `nomad_job.minio`, its firewall entry, root key, dashboard, alert, scrape job and edge route, and replaced `backup_minio` with `backup_s3`. The apply added 17, changed 4 and destroyed 22. Then `nomad job stop -purge` ran for minio and backup-minio. MinIO's ufw rules for 9000 and 9001 were deleted on orangepi4a by hand over SSH, because the firewall resource cannot remove rules.
- Step 3: `enable_consul_secrets.yml` re-ran without the `service "minio"` grant (changed=2).
- Step 5: the applications root deleted `default/backup-minio/seaweedfs`.
- Step 6: `nomad job start ov-dash`. The deployment is successful and the route returns 200. orangepi4a had 2.8 GB available once MinIO stopped.
- A forced `backup-s3` run (periodic-1792486100, alloc 91b5d9d2) exited 0, reading only `default/backup-s3/*`.

stdout.txt (this run): the applications state has 0 MinIO addresses and its plan reports no changes. The infrastructure plan lists only the 15 `null_resource.firewall` replacements that its `always_run` timestamp forces on every plan by design, and no other resource. `nomad job status` returns 404 for minio and backup-minio. The old key paths no longer serve data: Terraform's deletes were soft deletes. Afterwards `vault kv metadata delete` purged every version of default/backup-minio/{gcs,minio,seaweedfs} and default/minio/localstack, so no old copy of the live GCS key is left. The per-job default/<job>/minio entries keep soft-deleted versions of keys to a server that no longer runs.

The `minio_data` volume and its data are untouched, pending the operator-only `minio-volume-destroy`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/rm-verify/verify.sh`, which the command used
