---
type: plan
title: 'Plan: seaweedfs-buckets'
description: Create the SeaweedFS buckets, users, access keys and per-bucket policies from the applications Terraform root, and write each consumer's key to Vault.
slug: seaweedfs-buckets
epic: seaweedfs-migration
depends_on:
- seaweedfs-service
priority: 3
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:27+00:00'
---

# seaweedfs-buckets

Relayed from: none

## Intent

Give SeaweedFS the buckets and static-key users that MinIO has today, managed
by Terraform the way `deployments/applications/storage.tf` manages MinIO's.

Buckets: `datalake`, `models`, `registry`, `openviking`, `loki`, `tempo`.
`memex` and `mlflow-artifacts` are not recreated (operator, 2026-10-19).
Each keeps today's reader and writer split from `local.buckets`: a read-write
policy for writers and a read-only one for readers, one user and access key
each. Keys a running job reads go to Vault KV in
`deployments/applications/secrets.tf` under new paths
(`default/<job>/seaweedfs`), beside the MinIO ones, which stay until the
cutover.

The backup job's user is created here too, read-only on the four durable
buckets, and its key written to `default/backup-minio/seaweedfs` from
`deployments/applications/secrets.tf`. The infrastructure root applies first
and cannot reference this root's resources, so the user lives where the IAM
provider is. The backup job (infrastructure root) reads the key at run time
through Vault, not through Terraform, so on a rebuild from scratch it fails
until this root has applied. Say so in the comment above the secret.

The provider's address. The applications root runs with the brokered
`consul/creds/deploy` token, whose policy in
`bootstrap/playbooks/enable_consul_secrets.yml` reads only the `minio` and
`postgres-db` services, under `default_policy = "deny"`. Add
`service "seaweedfs" { policy = "read" }` there and run the playbook before
the first apply, so `data "consul_service" "seaweedfs"` finds the service
the way the MinIO provider finds `minio`. The admin key comes from an
ephemeral read of `default/seaweedfs/admin`, as `minio_admin` does today.

The MinIO resources and the `deployments/applications/modules/bucket` module
stay in place. The SeaweedFS side lives beside them, in the same files.

Outcome: after the playbook run and an apply, `aws s3 ls` with the admin key
lists exactly the six buckets. The backup user's key reads all four durable
buckets and is refused a write. For each user, its key can write and read its own bucket (or only
read, for a reader). The same key gets AccessDenied on another bucket. A
second `terraform plan` reports no changes. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- No Terraform provider manages SeaweedFS identities. No SeaweedFS provider
  turned up. The plan bets on the `hashicorp/aws` provider pointed at
  SeaweedFS's embedded IAM API (`aws_s3_bucket`, `aws_iam_user`,
  `aws_iam_access_key`, `aws_iam_user_policy`). If that API refuses one of
  those calls, or a second plan is never clean, the fallback is to render the
  identities file from Terraform into Vault and template it into the job. That
  moves work into `seaweedfs-service` and changes this ticket.
  Settled by `spike:seaweedfs-buckets/2`: `hashicorp/aws` ~> 6.0, with its
  s3 and iam endpoints on SeaweedFS's S3 port, created buckets, users, access
  keys and inline user policies, and a second plan was clean, also after a
  restart. Every IAM write fails unless the server runs with
  `-s3.iam.readOnly=false`. `aminueza/minio` is no fallback: its IAM
  resources fail against SeaweedFS.
- Policy enforcement. SeaweedFS's policy engine has to deny a user's key on
  another bucket, the way MinIO's bucket policies do today. If it only knows
  coarse per-identity actions, the per-bucket isolation the cluster relies on
  needs another design.
  Settled by `spike:seaweedfs-buckets/1`: on 4.48, both static identity
  actions and IAM `PutUserPolicy` isolate buckets (32 of 32 checks). A key
  scoped to one bucket gets AccessDenied on the other, and ListBuckets shows
  only the user's own bucket. An IAM-policy user also needs
  `s3:GetBucketLocation` granted, and the IAM API needs the server flag
  `-s3.iam.readOnly=false`.
