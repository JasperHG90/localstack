---
type: verdict
title: 'Verdict: minio-volume-destroy plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of minio-volume-destroy: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T09:37:24+00:00'
slug: minio-volume-destroy
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Nothing found that could break this plan. Nothing mounts `minio_data`, and
nothing in either Terraform root refers to it. The deployer may delete host
volumes. The data that matters is checked on SeaweedFS and in GCS. Removing
the block deletes only MinIO's own volume directory.

## Checked

- Live `nomad volume status -type host cb07eebf`: `minio_data` is ready on
  node 8bc24183 (orangepi4a), host path
  `/opt/nomad/data/host_volumes/cb07eebf-a72a-28f7-a223-a106d1ccbe2b`, "No
  allocations placed". `seaweedfs_data` on the same node has its own ID
  directory (e695de02), so deleting MinIO's path cannot touch SeaweedFS.
  `nomad job status` lists no minio job.
- Delete while referenced: Nomad refuses to delete a host volume that a
  running allocation claims. Here there are none, and the minio and
  backup-minio jobs were purged (`spike:minio-removal/4`).
- Does the `mkdir` plugin remove the directory: its delete removes the
  volume's path under the host volumes dir. The plan's outcome already checks
  that "the host directory is gone" on the node, so building will show it
  either way. That needs no spike.
- References: `minio_data` appears only in its own block in
  `deployments/infrastructure/services.tf:22`. No `depends_on` or job
  refers to it. `cli/tests/test_no_minio.py` allows it only in
  `services.tf`, and `cli/tests` is not in its scan list, so changing the
  allowed list and docstring is safe.
- Permissions: `nomad_acl_policy.deploy` in
  `deployments/infrastructure/machine_roles.tf` grants `host-volume-delete`.
- Data elsewhere: `spike:seaweedfs-cutover-openviking/3` (the tree and 25
  content hashes match after the restore, with OpenViking stopped before the
  last MinIO backup). `spike:seaweedfs-cutover-registry/2` (all 33 tags and
  192 layers match, and SeaweedFS holds MinIO's exact 399 keys).
  `spike:seaweedfs-cutover/4` and `/5` (GCS equals SeaweedFS file for file,
  and MinIO's counts were flat). models and datalake are empty. The only
  other MinIO buckets are loki and tempo, which the operator chose to drop.
- Vault purge: the live backup path is `default/backup-s3/*`. The
  `default/<job>/minio` and `default/minio/<user>` entries are already
  soft-deleted, and the backup-minio paths were already purged.

## Findings

None.

## Notes

The operator approved the deletion on 2026-10-20 ("Yes do it"), so
`Could invalidate this plan: none` is honest. The deletion cannot be undone,
and the operator has accepted that. Recovery depends on the GCS copy under
`minio/`, which `backup-s3` keeps up to date from SeaweedFS.
