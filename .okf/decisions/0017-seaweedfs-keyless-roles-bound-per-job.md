---
type: decision
title: "ADR 0017: SeaweedFS keyless access uses one trust-bound role per job"
description: "Keyless jobs reach SeaweedFS by trading their Nomad workload identity for a role whose trust policy names that job's nomad_job_id and sub, over SeaweedFS's claim mode, which splits the claim on commas and handed a job named evil,tempo tempo's policy."
tags: [adr, decision, seaweedfs, workload-identity, sts, oidc]
generated:
  by: claude-opus/5.5
  at: 2026-10-20T00:00:00Z
status: stable
sources:
  - resource: "deployments/infrastructure/services.tf"
  - resource: "deployments/infrastructure/services/seaweedfs.hcl"
  - resource: "cli/tests/test_seaweedfs_iam_config.py"
---

# ADR 0017: SeaweedFS keyless access uses one trust-bound role per job

## Context

tempo, loki and registry hold no stored S3 key. On MinIO each sends its Nomad
workload identity to STS, and MinIO's claim mode applies the policy named by
the token's `nomad_job_id`. Nomad signs that claim, so a job cannot pick
another job's bucket. SeaweedFS has to give the same guarantee
([ADR 0016](/decisions/0016-seaweedfs-replaces-minio.md)).

## Decision

SeaweedFS's IAM config, rendered by the `seaweedfs` job from
`local.seaweedfs_iam` in `deployments/infrastructure/services.tf`, trusts
Nomad's issuer with audience `seaweedfs` and holds one role and one policy
per keyless job. Each role's trust policy requires
`StringEquals oidc:nomad_job_id = <job>` and
`StringLike oidc:sub = global:default:<job>:*`, and its policy reaches only
that job's bucket. `policy.defaultEffect` is `Deny`. A client must send the
role's ARN and a session name.

Rejected: SeaweedFS's claim mode (`policyClaim` on the provider), the shape
MinIO uses. It splits the claim value on commas, and in
`spike:seaweedfs-workload-identity/2` a job named `evil,tempo` was given
tempo's policy. Also rejected: a trust policy that checks only issuer and
audience, because a jobspec author picks their own audience, so any job could
assume any role.

## Consequences

- Each client changes: the shell `credential_process` helpers (loki,
  registry) add `RoleArn` and `RoleSessionName`, and tempo sets
  `AWS_ROLE_ARN`, without which minio-go quietly falls back to anonymous
  credentials (`spike:seaweedfs-workload-identity/3`).
- A new keyless job needs one entry in `local.seaweedfs_keyless_jobs` and a
  SeaweedFS restart, since the config is a file the server reads at start.
- `cli/tests/test_seaweedfs_iam_config.py` renders the config and pins both
  trust conditions, the bucket scope and the absence of `policyClaim`.
- Proven live on 2026-10-20 with throwaway jobs: `wi-probe` wrote its bucket
  through its role, and `wi-probe-other` was refused that role
  (`spike:seaweedfs-workload-identity/6`).
