---
type: eval
title: 'Eval: minio-volume-destroy'
description: 'Definition of done for minio-volume-destroy: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:36:16+00:00'
slug: minio-volume-destroy
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 22c5e4f2bd90e3adfff7123e66dd67fc9581bba45ab041951ae786d15dd78e06
  at: '2026-10-20T09:36:16+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: No file under deployments/, bootstrap/, cli/src or .devcontainer/Dockerfile names MinIO except the GCS prefix minio/ in the backup-s3 and restore-s3 jobspecs, the minio-go library in tempo.hcl, the mc client in the Dockerfile and the alert uid listed under Grafana deleteRules; minio_data is no longer allowed.
  Fails when: minio_data or any other MinIO name remains in those paths
- r2 (judgment): After the apply, nomad volume status lists no minio_data, its host directory on orangepi4a is gone, no default/*/minio or default/minio/* path is left in Vault, and a second infrastructure terraform plan changes nothing but the always-run firewall rules.
  Fails when: any of those fails, or the evidence is not recorded in the review
- r3 (judgment): The pages that said the volume is kept (.okf/components/minio.md, host-volumes.md, nodes/orangepi4a.md, summary.md) say it was deleted on the operator's approval, and .okf/log.md records it.
  Fails when: a page still says minio_data or its data remains
