---
type: plan
title: 'Plan: ovsq-keyless-local-sync'
description: Give local ovsq runs 15-minute SeaweedFS STS sessions minted from the operator's Vault session, writing one ov-sync prefix the consumer maps once.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T18:31:00+00:00'
slug: ovsq-keyless-local-sync
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# ovsq-keyless-local-sync

Relayed from: none

## Intent

`ovsq` (openviking_extensions, `packages/ov-sync-queue`) uploads a local
folder to `ov-sync/<prefix>/<subdir>/`, where `ov-sync-consumer` picks it up,
the same route the openviking-sync action takes for CI. It is for repositories
CI cannot sync. Its upstream how-to hands it a static key in SeaweedFS's
`s3.json`. The operator rejected that: no key that lasts is stored anywhere.

This ticket gives ovsq the CI chain's credential shape (ADR 0028,
`.okf/decisions/0028-ci-syncs-repo-folders-to-ov-sync-with-a-manifest-and-a-vault-identity-token.md`),
minted by the operator instead of a workflow:

- A Vault identity-token role `local-ov-sync` in
  `deployments/infrastructure/oidc.tf`, beside
  `vault_identity_oidc_role.ci_ov_sync`. It uses client id `seaweedfs`, a
  ttl of 900 and a literal `local_ov_sync = "JasperHG90/local"` claim. That
  claim is separate from `ci_repository`, so neither token fits the other's
  role.
- A policy that reads only `identity/oidc/token/local-ov-sync`, carried by an
  internal group whose only member is `vault_identity_entity.operator`, in
  `deployments/infrastructure/identity.tf`. It follows the `openviking_user`
  policy and group there. The operator does not have to be in `admin`.
- A SeaweedFS role and policy `local-ov-sync` in `local.seaweedfs_iam`
  (`deployments/infrastructure/services.tf`). The trust policy requires
  `oidc:local_ov_sync = "JasperHG90/local"` and `oidc:sub` equal to the
  operator entity's id by `StringEquals`. Vault sets a token's `sub` to the
  entity that minted it, so a seaweedfs-audience token that an admin-group
  member mints, or that the operator mints for a `ci-*` role, is refused. The
  policy allows `GetObject`, `PutObject` and `DeleteObject` on
  `arn:aws:s3:::ov-sync/JasperHG90/local/*` and nothing else. There is no
  List, because ovsq never lists the bucket and keeps its own manifest.
- One entry in `nomad_job.ov_sync_consumer`'s `prefixes`
  (`deployments/applications/services.tf`) that maps `JasperHG90/local/` to
  a dedicated folder, `viking://user/jasper/resources/local/`. Each folder
  picks its path under that folder with ovsq's `subdir` and keeps its own
  `source`, so a new folder needs no Terraform change. Why the root is not
  `viking://user/jasper/resources/` itself is under Could invalidate this plan.
- A `localstack ov-sync-env` command
  (`new:cli/src/localstack_cli/commands/ov_sync_env.py`, registered in
  `LAZY_SUBCOMMANDS` in `cli/src/localstack_cli/main.py`). It reads the
  token with the session's Vault token (`vault.read_creds` in
  `cli/src/localstack_cli/auth/vault.py`) and posts it to SeaweedFS's STS
  `AssumeRoleWithWebIdentity` at `https://s3.lab.orangecluster.nl` with
  `DurationSeconds=900`. The identity token's ttl does not set the session
  length: SeaweedFS 4.48 takes the request's `DurationSeconds`, else the
  `tokenDuration` of `"1h"` in `deployments/infrastructure/services/seaweedfs.hcl`,
  and ignores the token's `exp`. 900 is SeaweedFS's minimum. It prints
  `export AWS_ACCESS_KEY_ID=...`, `AWS_SECRET_ACCESS_KEY` and
  `AWS_SESSION_TOKEN`, so `eval "$(localstack ov-sync-env)"` precedes an ovsq
  run. It follows `localstack env` (`cli/src/localstack_cli/commands/env.py`):
  exports on stdout, diagnostics on stderr, and empty stdout with a non-zero
  exit on failure. A command beats a shell recipe here: the CLI already holds
  the Vault session, the recipe would need `aws` and `jq` on the laptop, and
  pytest can cover a command. A first sync that outlives the 15 minutes
  stops partway, keeps the progress its manifest recorded, and continues
  after a fresh `eval` and rerun; the how-to says so.
- A how-to, `new:docs/how-to/sync-a-local-folder-to-openviking-with-ovsq.md`,
  that follows `.claude/rules/how-to-skeleton.md`. Also a decision record
  made with `kmctl new decision` under `.okf/decisions/` that names the static
  key it rejects, the keyless route in `docs/explanation/workload-identity.md`,
  the ownership row in `.okf/architecture/deployment-layers.md`, and
  `.okf/summary.md`.

No new `.tf` file (`.claude/rules/terraform-file-layout.md`). SeaweedFS reads
roles only at start, so the infrastructure apply restarts it, as every change
to `local.seaweedfs_iam` does.

Code already settles two of the briefing's concerns:
- `Mapping.Resolve` in
  `applications/ov-sync-consumer/internal/consumer/mapping.go` looks up the
  first two key segments exactly, so `JasperHG90/local/` and
  `JasperHG90/localstack/` are separate prefixes. Keys under
  `JasperHG90/local/_state/`, where ovsq keeps its manifest, are skipped.
- ovsq's internal/s3store/s3store.go (upstream) builds its credentials from minio-go's
  `credentials.EnvAWS`, which reads `AWS_SESSION_TOKEN`. Its internal/config/config.go
  requires a two-part `prefix`, which `JasperHG90/local` is.

The outcome that shows it worked: after `eval "$(localstack ov-sync-env)"`,
an ovsq run with prefix `JasperHG90/local` and subdir `projects/notes` writes
its files, and they appear under
`viking://user/jasper/resources/local/projects/notes/`. The same credentials
get AccessDenied on a put under `ov-sync/JasperHG90/localstack/`.

## Problems

- P1: No SeaweedFS role lets a local process write the ov-sync bucket without a static key: only Nomad jobs and `ov_sync` CI callers have STS roles
- P2: `nomad_job.ov_sync_consumer` maps no prefix for local folders, so whatever ovsq writes is skipped
- P3: The operator has no way to turn their Vault session into the three `AWS_*` variables ovsq reads
- P4: Nothing in the repository documents the keyless local route, and ovsq's upstream how-to prescribes the static key the operator rejected

## Goals

- G1: The operator syncs a folder that no CI can reach into OpenViking, with credentials that expire in minutes and are stored nowhere
- G2: Local credentials cannot write a CI prefix, and a CI token cannot assume the local role
- G3: The next reader finds the local route, and why it carries no static key, in the docs and the knowledge bundle

## Outcomes

### O1: Vault mints a 15-minute `local-ov-sync` identity token for the operator entity only
- kind: support
- goal: G1
- fixes: P1
- needs: none
- touches: `deployments/infrastructure/oidc.tf`, `deployments/infrastructure/identity.tf`
- checked by: `new:cli/tests/test_local_ov_sync.py` asserts the role's client id `seaweedfs`, ttl 900 and literal `local_ov_sync` template, a policy reading only that token path, and a group whose sole member is the operator entity; `scripts/tf_validate.sh`
- seen by: nobody

### O2: SeaweedFS role `local-ov-sync` trusts only the local claim and the operator's `sub`, and writes only `ov-sync/JasperHG90/local/*`
- kind: support
- goal: G2
- fixes: P1
- needs: O1
- touches: `deployments/infrastructure/services.tf`, `cli/tests/fixtures/seaweedfs_iam.py`
- checked by: `cli/tests/test_seaweedfs_iam_config.py` renders the IAM config and asserts the role's two `StringEquals` conditions, its Get/Put/Delete-only policy on the one prefix, and that no `ci-*` role names `local_ov_sync`
- seen by: nobody

### O3: The consumer maps `JasperHG90/local/` to `viking://user/jasper/resources/local/`
- kind: support
- goal: G1
- fixes: P2
- needs: none
- touches: `deployments/applications/services.tf`
- checked by: `new:cli/tests/test_local_ov_sync.py` asserts the `prefixes` entry, and that no mapped folder is an ancestor of another mapped folder or of the hermes save root `viking://user/jasper/resources/`
- seen by: nobody

### O4: `localstack ov-sync-env` prints export lines for ov-sync credentials that last 15 minutes
- kind: behaviour
- goal: G1
- fixes: P3
- needs: O1, O2, O3
- touches: `new:cli/src/localstack_cli/commands/ov_sync_env.py`, `cli/src/localstack_cli/main.py`, `localstack ov-sync-env`
- checked by: `new:cli/tests/commands/test_ov_sync_env_command.py`, with Vault and STS faked: it posts `DurationSeconds=900` to STS, three export lines on success, and empty stdout with a non-zero exit on a Vault 403 and on an STS refusal; then a live ovsq run lands under `viking://user/jasper/resources/local/` and the same credentials get AccessDenied under `ov-sync/JasperHG90/localstack/` and the returned `Expiration` is about 15 minutes out
- seen by: operator

### O5: A how-to, a decision record and the architecture pages describe the local route
- kind: support
- goal: G3
- fixes: P4
- needs: O4
- touches: `new:docs/how-to/sync-a-local-folder-to-openviking-with-ovsq.md`, `docs/explanation/workload-identity.md`, `.okf/architecture/deployment-layers.md`, `.okf/summary.md`
- checked by: `cli/tests/test_how_to_skeleton.py`, `kmctl check`, `just pre_commit`
- seen by: operator

## Could invalidate this plan

The consumer root was settled by the operator on 2026-11-27: `JasperHG90/local/` maps to `viking://user/jasper/resources/local/`, never `resources/` itself, because `CatchUp` (`applications/ov-sync-consumer/internal/consumer/catchup.go`) deletes every file under a mapped root that has no bucket object.

- If SeaweedFS 4.48 counts a `StringEquals` condition on a claim the token lacks as a match, the claim separation fails: a `local-ov-sync` token could assume a `ci-*` role. spike:ci-openviking-sync/1 showed only a different value for a present `ci_repository` claim being refused. It never presented a token without that claim. Settled by spike:ovsq-keyless-local-sync/1: a token lacking the claim, or carrying the wrong `sub`, is refused by each role, and the local credential is refused outside `ov-sync/JasperHG90/local/`.
