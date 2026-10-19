---
type: verdict
title: 'Verdict: minio-removal plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of minio-removal: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T17:55:57+00:00'
slug: minio-removal
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan can go ahead once two things are settled. The approach holds:
remove MinIO after the cutover, and leave the volume to minio-volume-destroy.
The plan does not need splitting. But "Could invalidate this plan: none" is
too optimistic. It does not say how the minio_* resources leave state, or in
what order the two roots and the playbook run (p1). That is a real risk, and
a spike can settle it. Its done check cannot be decided for the backup job,
which keeps the minio name (p2).

## Checked

- The listed scope matches the repo: nomad_job.minio, the firewall entry at
  infrastructure/services.tf:326, the root key at infrastructure/secrets.tf:9-20,
  the provider and the data source, applications/storage.tf, and the bucket
  module, whose own required_providers in modules/bucket/providers.tf goes
  with it. Also the Consul grant at enable_consul_secrets.yml:49, the haproxy
  route and backend, the Prometheus scrape job, the Grafana dashboard, and mc
  in the Dockerfile.
- modules/bucket/main.tf: minio_s3_bucket has no force_destroy.
- The sibling plans: memex and mlflow-artifacts are neither moved nor backed
  up (by operator decision), so their objects are still in MinIO.
- The applications provider config depends on infrastructure-owned state:
  the Consul service and the Vault root key.
- Terraform v1.16.5 is installed, so removed blocks are available.

## Findings

- p1: the teardown method and order are missing. A destroy fails on
  non-empty buckets, and force_destroy would delete the data that must stay.
  If the infrastructure root or the playbook goes first, the minio_* resources
  are stuck in state. A spike should answer the question in the finding.
- p2: the backup job, its jobspec, its Vault paths and its GCS prefix keep
  the minio name. Either rename them or accept them, before the grep outcome
  can pass or fail.

## Notes

The grep outcome will also find bootstrap/.env.example and bootstrap/README.md
(MINIO_ROOT_PASSWORD), which the plan does not list. The grep sends the builder
to them, so they are not a finding. .devcontainer/.env.example and
.claude/rules/terraform-file-layout.md are outside the grep. The rules file
uses MinIO as an example of the file split and is still valid history.
