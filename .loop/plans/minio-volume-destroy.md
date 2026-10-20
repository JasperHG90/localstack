---
type: plan
title: 'Plan: minio-volume-destroy'
description: Destroy the minio_data host volume and its data on orangepi4a once the operator confirms the SeaweedFS restore and the GCS copy.
slug: minio-volume-destroy
epic: seaweedfs-migration
depends_on:
- minio-removal
priority: 7
status: draft
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:52:42+00:00'
---

# minio-volume-destroy

Relayed from: none

## Intent

Remove `nomad_dynamic_host_volume.minio_data` from
`deployments/infrastructure/services.tf` and apply, which deletes MinIO's
data on orangepi4a. This cannot be undone, so it waited for the operator,
who approved it on 2026-10-20 ("Yes do it") after `minio-removal` landed.
Every durable bucket is on SeaweedFS and in GCS; Loki's and Tempo's old 30
days were not moved, by the operator's decision, and go with the volume.

Also: purge the soft-deleted per-job MinIO keys left in Vault
(`default/<job>/minio` and `default/minio/<user>`, every version, with
`vault kv metadata delete`), drop `minio_data` from the allowed names in
`cli/tests/test_no_minio.py`, and update the pages that say the volume is
kept (`.okf/components/minio.md`, `.okf/components/host-volumes.md`,
`.okf/nodes/orangepi4a.md`, `.okf/summary.md`, `.okf/log.md`).

Outcome: `nomad volume status` lists no `minio_data`, the host directory is
gone, no `default/*/minio` path is left in Vault, a second `terraform plan`
in the infrastructure root changes nothing but the always-run firewall
rules, and `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- none
