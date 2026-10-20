---
type: eval
title: 'Eval: seaweedfs-cutover-registry'
description: 'Definition of done for seaweedfs-cutover-registry: 2 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T04:37:31+00:00'
slug: seaweedfs-cutover-registry
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 559b07c1e5352efd2727ef6b2512b1bef2272079ef8be3e28f92544fce7096d7
  at: '2026-10-20T04:37:31+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: registry.hcl requests a workload identity with audience seaweedfs, its credential_process helper sends RoleArn for the registry role and RoleSessionName=registry, and regionendpoint comes from a template variable.
  Fails when: the audience is still minio, the helper lacks RoleArn or RoleSessionName, or 192.168.2.29:9000 is hardcoded
- r2 (judgment): After the stop, backup, restore and start: rclone check exits 0 for registry, an image pushed before the switch pulls by tag and by digest, a new push succeeds with its blobs in SeaweedFS's registry bucket, and MinIO's registry count stays fixed.
  Fails when: any of those fails, MinIO's count rises, or the evidence is not recorded in the review
