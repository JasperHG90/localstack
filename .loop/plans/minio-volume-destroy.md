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
data on orangepi4a. This cannot be undone, so it waits until the operator
has checked SeaweedFS and the GCS copy and promotes this stub.

Outcome: `nomad volume status` lists no `minio_data`, the host directory is
gone, and a second `terraform plan` in the infrastructure root is clean.

## Could invalidate this plan

- none
