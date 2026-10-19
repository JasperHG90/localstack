---
type: verdict
title: 'Verdict: seaweedfs-buckets plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-buckets: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T18:00:29+00:00'
slug: seaweedfs-buckets
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach holds, and both listed risks are settled by spikes that answer
them. Two scope gaps the plan does not list must be decided before building:
how the applications root reaches SeaweedFS under the scoped Consul token (p1),
and which root mints the backup job's read-only key (p2). Revise, not rethink.
No split is needed.

## Checked

- `spike:seaweedfs-buckets/2` (README, stdout, run.json): hashicorp/aws ~> 6.0
  created buckets, users, keys and inline policies on 4.48. The second plan was
  clean, also after a restart. aminueza/minio IAM fails, as claimed.
- `spike:seaweedfs-buckets/1`: 32/32 isolation checks for static and IAM
  users. The `s3:GetBucketLocation` trap is covered, because today's MinIO
  read-only policy in `modules/bucket/main.tf` already grants it.
- seaweedfs-service plan: it owns `-s3.iam.readOnly=false` and the admin key at
  `default/seaweedfs/admin`, which an ephemeral read can feed to the aws
  provider the way `minio_admin` feeds minio.
- `deployments/applications/providers.tf` and `services.tf`: minio's address
  comes from `data.consul_service.minio`.
- `bootstrap/playbooks/enable_consul_secrets.yml`: the deploy policy reads only
  `minio` and `postgres-db`. Consul runs `default_policy = "deny"`.
- `deployments/infrastructure/secrets.tf:360` and `services.tf:713`: the backup
  job uses MinIO's root key, minted in the infrastructure root.
- `deployments/infrastructure/identity.tf`: the deployer's Vault policy covers
  `secret/data/default/*`.

## Findings

- p1: the aws provider's endpoint. A `consul_service "seaweedfs"` lookup
  returns empty under the deploy token, so `service[0]` fails. Either change the
  Ansible deploy policy and re-run it (out-of-Terraform scope that no plan
  lists), or use a fixed address.
- p2: backup key placement. `deployments/infrastructure/secrets.tf` cannot
  reference an IAM key minted in the applications root. Each fix (mint in
  applications, a second aws provider in infrastructure, or keep the admin key)
  changes scope or the read-only contract.

## Notes

Neither gap needs a spike. Consul's ACL filtering follows from the policy text
and `default_policy = "deny"`. The eval has no rows yet.
