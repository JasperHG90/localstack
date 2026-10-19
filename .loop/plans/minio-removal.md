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

Remove from the infrastructure root: `nomad_job.minio`, its jobspec
`deployments/infrastructure/services/minio.hcl`, its firewall rule, the
Vault KV root key and the backup job's MinIO key. Remove from the
applications root: the `aminueza/minio` provider and its config in
`deployments/applications/providers.tf`, the `data "consul_service"
"minio"` lookup and root-key read in `deployments/applications/services.tf`,
every `minio_*` resource in `deployments/applications/storage.tf`, the
`deployments/applications/modules/bucket` module, and the MinIO keys in
`deployments/applications/secrets.tf`. Also remove the Consul `deploy`
policy's `service "minio"` grant in
`bootstrap/playbooks/enable_consul_secrets.yml`, MinIO's dashboard, alerts
and scrape job, the `minio.lab` edge route, and `mc` in
`.devcontainer/Dockerfile`.

The `minio_data` host volume and the data on it stay. Destroying them is the
one irreversible step, and it is the stub `minio-volume-destroy`, which only
the operator promotes.

Docs: replace the three MinIO keyless how-tos with SeaweedFS ones (or one
page if the two client routes have merged), update
`docs/explanation/workload-identity.md`, and mark
`.okf/components/minio.md` superseded with a link to the SeaweedFS
component page that `seaweedfs-service` writes. Write a decision record for the removal.

Outcome: `grep -ri minio deployments/ bootstrap/ cli/src docs/` finds only
historical mentions. `terraform plan` in both roots shows only MinIO
resources being destroyed, then nothing on a second plan. `nomad job status
minio` reports no such job. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- none
