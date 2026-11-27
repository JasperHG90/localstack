---
type: decision
title: "ADR 0034: Local ovsq syncs use a keyless operator STS role, not a static key"
description: "The operator laptop writes ov-sync/JasperHG90/local/ with 15-minute STS credentials minted from their Vault session, not with the static S3 key ovsq upstream prescribes."
tags: [decision]
generated:
  by: process:kmctl/0.18.0
  at: 2026-11-27T19:16:17Z
status: stable
sources:
  - resource: "deployments/infrastructure/services.tf"
  - resource: "deployments/infrastructure/oidc.tf"
  - resource: "deployments/infrastructure/identity.tf"
  - resource: "cli/src/localstack_cli/commands/token.py"
  - resource: "cli/src/localstack_cli/auth/sts.py"
---

# ADR 0034: Local ovsq syncs use a keyless operator STS role, not a static key

## Context

The operator wants folders that no CI workflow can reach, such as notes and
repositories without the openviking-sync workflow, in OpenViking through the
ov-sync queue. The client is `ovsq` (openviking_extensions,
`packages/ov-sync-queue`). Its upstream how-to adds a static S3 key, scoped to
one prefix, to SeaweedFS's `s3.json`, because it assumed a laptop has no
keyless login. The operator does have one: a Vault session.
[ADR 0028](0028-ci-syncs-repo-folders-to-ov-sync-with-a-manifest-and-a-vault-identity-token.md)
already turned down a static key per caller for CI, and the manifesto puts
short-lived credentials ahead of static ones.

## Decision

The laptop takes the CI route with a different identity. Vault role
`local-ov-sync` mints a token with audience `seaweedfs` and the literal claim
`local_ov_sync = "JasperHG90/local"`. Only a group whose one member is the
operator entity can read it. SeaweedFS's role `local-ov-sync` trusts the
claim and the operator entity's `sub`, both by `StringEquals`, and allows
Get, Put and Delete on `ov-sync/JasperHG90/local/*` only.
spike:ovsq-keyless-local-sync/1 showed that a CI token can't take this role,
a local token can't take a `ci-*` role, and another entity's token is
refused. `localstack token s3 local-ov-sync` mints the token and swaps it with
`DurationSeconds=900`, because SeaweedFS ignores the token's expiry and would
otherwise grant its default of an hour.

The consumer maps `JasperHG90/local/` once to
`viking://user/jasper/resources/local/`, and each folder chooses its place
with ovsq's `subdir`. It is not mapped to `resources/` itself, because the
consumer's catch-up pass deletes every file under a mapped folder that has no
object behind it, and that would delete the hermes saves.

Rejected: the static key ovsq prescribes. It works with no extra step before
a run, but it is a long-lived key on a laptop that can write the prefix until
someone rotates it.

## Consequences

- No S3 key exists for local syncs. Each run starts with
  `eval "$(localstack token s3 local-ov-sync)"`, and a sync that runs past 15 minutes
  continues after a fresh eval.
- Every local folder shares one credential scope, so any of them can
  overwrite another under `JasperHG90/local/`. Separate `subdir` and
  `source` values keep them apart.
- Adding a local folder needs no Terraform change. A local path outside
  `resources/local/` would need a consumer change first.
- The upstream ovsq how-to still describes the static key until its docs are
  changed to point here.
