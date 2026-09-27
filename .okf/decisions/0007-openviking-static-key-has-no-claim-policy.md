---
type: decision
title: "ADR 0007: OpenViking's static MinIO key carries no claim-mode policy"
description: OpenViking's S3 config cannot take short-lived credentials, so its job reads the openviking MinIO user's static key from Vault. No minio_iam_policy named openviking sits beside it, because one would read as live while granting nothing.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, openviking, minio, workload-identity]
status: stable
decision_status: Accepted
decided_on: 2026-09-05
sources:
  - id: openviking
    resource: git:3ec5d1e:docs/openviking.md
    last_modified: 2026-09-12
---

# ADR 0007: OpenViking's static MinIO key carries no claim-mode policy

- Status: Accepted
- Date: 2026-09-05

> Written retrospectively from docs/openviking.md, dated 2026-09-12.

## Context

Every other keyless service here exchanges a Nomad Workload Identity JWT for
short-lived MinIO credentials. OpenViking cannot:

- `S3Config.validate_config` makes `access_key` and `secret_key` mandatory
  whenever `backend` is `s3`, so a keyless config is rejected before the client
  is built.
- The Rust client behind AGFS builds `Credentials::new(ak, sk, None, ...)`.
  The `None` is the session token, which STS credentials require.
- `session_token` is a forbidden extra key on `S3Config`, and `backend` accepts
  only `local`, `s3` and `memory`, so no config route reaches the SDK's default
  credential chain.

## Decision

So the job reads the existing `openviking` MinIO user's key from Vault. There
is deliberately **no** `minio_iam_policy` named `openviking`: MinIO's claim mode
resolves a policy by the job id, so one would read as live while granting
nothing to a service that authenticates with a static key.

Rejected alternative: keeping a `minio_iam_policy` named `openviking` beside
the static key, the way claim-mode services carry one. It would look live and
grant nothing. Workload identity itself was not a choice: no config route
reaches it.

## Consequences

This is a step back from the direction the rest of the cluster is moving in,
forced rather than chosen. If upstream ever makes those two fields optional and
threads a session token, the route back is one config block.
