---
type: plan
title: 'Plan: seaweedfs-workload-identity'
description: Let a Nomad job exchange its workload identity JWT at SeaweedFS's STS for credentials scoped to its own bucket and no other.
slug: seaweedfs-workload-identity
epic: seaweedfs-migration
depends_on:
- seaweedfs-buckets
priority: 4
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:30+00:00'
---

# seaweedfs-workload-identity

Relayed from: none

## Intent

`tempo`, `loki` and `registry` log in to MinIO without a stored key. Each
sends its Nomad workload identity JWT (audience `minio`) to MinIO's STS
`AssumeRoleWithWebIdentity` with no RoleArn. MinIO runs in claim mode and
applies the policy named by the JWT's `nomad_job_id` claim
(`deployments/infrastructure/services/minio.hcl`,
`deployments/applications/storage.tf`). One job cannot get another's bucket,
because Nomad signs the claim and the job cannot choose it.

SeaweedFS has an STS that accepts OIDC tokens, but it works by roles with
trust policies, plus a `roleMapping` that picks a role from a claim value.
This ticket rebuilds the same guarantee on SeaweedFS:

- Nomad's issuer configured as an OIDC provider in SeaweedFS's IAM config,
  read from `https://nomad.lab.orangecluster.nl/.well-known/openid-configuration`
  as MinIO does today.
- One role and one policy per job (`tempo`, `loki`, `registry`), each scoped
  to that job's bucket. Each role's trust policy is bound to the job's
  `nomad_job_id` (or `sub`) claim, not only to the issuer and audience.
- A new audience, `seaweedfs`, so a job's MinIO identity and its SeaweedFS
  identity stay apart during the cutover.

No job switches here. The cutover ticket does that. Update
`.okf/components/workload-identity-chain.md` and write a decision record for
how the per-job binding works.

Outcome: from a throwaway Nomad job named `tempo`, the JWT exchange at
SeaweedFS's STS returns credentials that read and write `tempo` and get
AccessDenied on `loki`. A job named something else gets no credentials for
the `tempo` role, even when it sets audience `seaweedfs` and passes the
`tempo` role ARN. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- Per-job binding. A trust policy that checks only issuer and audience lets
  any job assume any role, because a jobspec author picks their own audience.
  That is the hole MinIO's POC2 target documents. If SeaweedFS's trust
  policies cannot condition on `nomad_job_id` or `sub`, and `roleMapping`
  cannot stand in for them on the STS path, keyless access cannot be made
  safe on SeaweedFS. The fallback is per-job static keys from Vault, a step
  back the operator must choose.
  Settled by `spike:seaweedfs-workload-identity/2`: on 4.48, a role whose
  trust policy has `StringEquals {"oidc:nomad_job_id": "<job>"}` and
  `StringLike {"oidc:sub": "global:default:<job>:*"}` (Principal
  `{"Federated": "<provider name>"}`) binds the role to one job. A loki token
  asking for the tempo role gets 403, as do a forged token, another namespace
  and `aud=minio` (17 of 17 checks). STS needs a RoleArn and ignores
  `roleMapping`. Do not use the provider's `policyClaim` (MinIO-style claim
  mode): it splits the claim on commas, and a job id `evil,tempo` got
  tempo's policy. The IAM config also needs `policy.defaultEffect: Deny` and
  an STS signing key, which `seaweedfs-service` does not set today.
- Client fit. `tempo` uses minio-go's web identity provider with no RoleArn.
  `loki` and `registry` use a shell `credential_process` helper that calls
  STS by query string and parses the XML with `sed`
  (`deployments/applications/services/loki.hcl`). If SeaweedFS's STS needs a
  RoleArn, wants a POST body or answers in another shape, each client needs
  changes, and minio-go may not send a RoleArn at all.
  Real but cheap, per `spike:seaweedfs-workload-identity/3`: SeaweedFS
  refuses any request without `RoleSessionName` (400) or, outside claim
  mode, without `RoleArn` (403). The shell helper works once it adds
  `&RoleArn=<role>&RoleSessionName=<job>` to its query string: the empty
  POST and the `sed` over the XML are unchanged. minio-go v7.1.0 (Tempo
  2.10.8) sends a generated `RoleSessionName` only when `AWS_ROLE_ARN` is set,
  and with it set got credentials and wrote to `tempo`. Without it the chain
  falls back to anonymous credentials and fails quietly, so the cutover's
  check for Tempo must see a real write.
  Confirmed by `spike:seaweedfs-workload-identity/4`: with those two changes,
  the loki helper and minio-go each got credentials for their own per-job
  role and wrote to their own bucket, and each was refused (403) on the
  other job's role.
- Discovery. SeaweedFS reads a `jwksUri`, defaulting to
  {issuer}/.well-known/jwks.json. Nomad serves its keys at
  /.well-known/jwks.json behind the edge. If SeaweedFS cannot reach or parse
  them from orangepi4a, the exchange fails for every job.
  Settled by `spike:seaweedfs-workload-identity/1`: discovery's `jwks_uri`
  equals {issuer}/.well-known/jwks.json, the issuer matches, and all four
  keys are RSA/RS256, which SeaweedFS parses (it parses RSA and EC, not OKP).
  The Let's Encrypt cert verifies against system roots, so no `tlsCaCert`.
  If Nomad ever adds an EdDSA key, SeaweedFS rejects those tokens. Write that
  into the component page as a trap.
