---
type: decision
title: "ADR 0028: CI syncs repo folders to a shared ov-sync bucket with a manifest and a Vault identity token swapped at SeaweedFS STS"
description: "The openviking-sync action writes git-tracked folders to the caller's own prefix of ov-sync, tracks what it wrote in a manifest object, and gets S3 credentials by swapping a Vault identity token at SeaweedFS STS."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-15T22:38:26Z
status: stable
sources:
  - resource: ".github/actions/openviking-sync/action.yml"
  - resource: ".github/actions/openviking-sync/sync.py"
  - resource: "deployments/infrastructure/services.tf"
  - resource: "deployments/infrastructure/oidc.tf"
  - resource: "deployments/infrastructure/machine_roles.tf"
---

# ADR 0028: CI syncs repo folders to a shared ov-sync bucket with a manifest and a Vault identity token swapped at SeaweedFS STS

## Context

Repositories should reach OpenViking with their `docs/` and `.okf/` without CI
talking to OpenViking. [ADR 0026](/decisions/0026-repo-docs-reach-openviking-through-a-webhook-receiver-a-jetstream-queue-and-a-consumer.md)
has `ov-sync-consumer` read the `ov-sync` bucket's events and write
OpenViking, so CI only has to put files in the bucket. The bucket is shared:
`s3://ov-sync/<owner>/<repo>/...`, and a repository may write only its own
prefix. A file removed from a synced folder must leave the bucket too.
[ADR 0027](/decisions/0027-ci-reaches-the-lab-through-a-public-lab-auth-action-and-per-caller-vault-roles.md)
gives a job a Vault token, but nothing yet turned that into S3 access.

## Decision

A second composite action, `.github/actions/openviking-sync`, runs after
`lab-auth`. Its `sync.py` hashes every git-tracked file under the chosen
folders, compares the hashes with a manifest object,
`<owner>/<repo>/_state/manifest.json` (path to sha256, a missing one is
empty), uploads what changed, deletes what the manifest lists and the
checkout no longer has, and writes the manifest back. After a failed upload or
delete it still writes the manifest, holding what is true in the bucket (the
old entry for a failed upload, the entry kept for a failed delete), and exits
non-zero. A file uploaded by a failed run and deleted before the next run is
then still removed. The workflow's concurrency group runs one at a time, so two
runs never race on the manifest.

The S3 credential is a Vault identity token swapped at SeaweedFS STS. Each
`var.vault_ci_callers` entry with `ov_sync = true` gets a Vault identity-token
role `ci-<key>` (audience `seaweedfs`, literal `ci_repository` claim, 15
minutes), a policy on its `jwt-github` role that reads only that token path,
and a SeaweedFS role and policy `ci-<key>`. The role's trust pins
`oidc:ci_repository` by `StringEquals`. The policy allows `GetObject`,
`PutObject` and `DeleteObject` on `arn:aws:s3:::ov-sync/<owner>/<repo>/*` and
nothing else. SeaweedFS trusts Vault's identity issuer as a second OIDC
provider beside Nomad's (spike:ci-openviking-sync/1).

Rejected:

- **A static IAM user and key per caller in Vault KV.** It works with what
  SeaweedFS had already shown, but it is a long-lived key per repository.
- **SeaweedFS STS trusting GitHub's issuer directly.** It puts a second list
  of who may write outside Vault, beside `var.vault_ci_callers`.
- **Keeping sync state in `actions/cache` or an artifact.** The cache is
  evicted and scoped by branch, and an artifact expires, so a lost state would
  leave deleted files in the bucket. The manifest is kept beside the files it
  describes, and the credential needs no List because of it.

## Consequences

- No S3 key exists for CI. A job's credential lasts minutes and reaches one
  prefix.
- `ov_sync` callers carry one extra Vault policy, so ADR 0027's "`default`
  policy only" holds for the other callers.
- The manifest is the only record of what CI wrote. An object put in a prefix
  by hand is never deleted by the action, and a lost manifest leaves objects
  behind until someone removes them.
- `ov-sync-consumer` skips keys under `_state/`, so the manifest never reaches
  OpenViking.
- SeaweedFS reads its IAM config only at start, so adding a caller restarts
  it.
- A new repository needs an `ov_sync` caller entry and a prefix mapping in the
  consumer's `prefixes`, or its files land in the bucket and go nowhere.
