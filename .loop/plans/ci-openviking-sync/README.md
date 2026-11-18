---
type: plan
title: 'Plan: ci-openviking-sync'
description: A second composite GitHub Action, openviking-sync, that runs after lab-auth and mirrors chosen folders into the caller's own prefix of the ov-sync bucket using a stored manifest, and a workflow that uses both to sync docs/ and .okf/ on push to main.
slug: ci-openviking-sync
status: draft
epic: ci-lab-access
depends_on:
- ci-tailscale-access
- ov-sync-consumer
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:18:40+00:00'
---

# ci-openviking-sync

Relayed from: none

## Intent

Operator answers, 2026-11-15 (they replace the 2026-10-20 design, which ran
`ovsync` against OpenViking from CI):
- CI never talks to OpenViking. It writes files to a shared SeaweedFS bucket,
  `ov-sync`, and `ov-sync-consumer` (planned in parallel) reads the bucket's
  events from JetStream and writes OpenViking. That ticket creates the bucket
  and the filer webhook in `deployments/infrastructure/services/seaweedfs.hcl`,
  and holds the OpenViking credential and the path mapping.
- The bucket is shared by repos: `s3://ov-sync/<owner>/<repo>/{docs,.okf}/...`.
  Each caller may write only its own `<owner>/<repo>/` prefix.
- Deletions mirror: a file removed from a synced folder is removed from the
  bucket.
- The action lives in this repo, next to `lab-auth`.

`ci-tailscale-access` builds `lab-auth`, which puts the caller's job on the
tailnet with `VAULT_ADDR` and `VAULT_TOKEN` set. This ticket builds
`openviking-sync`, which a job runs after it, and uses both here to sync
`docs/` and `.okf/` on every push to `main`.

### The action

`new:.github/actions/openviking-sync/action.yml`, with its logic in
`new:.github/actions/openviking-sync/sync.py` (standard library only, calling
the `aws` CLI the GitHub runner image already has) and a usage snippet in
`new:.github/actions/openviking-sync/README.md`. Inputs: `folders` (default
`docs` and `.okf`), `bucket` (default `ov-sync`), `s3-endpoint` (default
`https://s3.lab.orangecluster.nl`), and `credential-role` (default: the
caller's Vault identity-token role, below). Steps:

1. Fail early unless `VAULT_ADDR` and `VAULT_TOKEN` are set.
2. Get short-lived S3 credentials (below) and mask them.
3. Read the object _state/manifest.json under the caller prefix, a JSON map of
   repo-relative path to sha256. A missing manifest is an empty map.
4. Hash every git-tracked file under `folders`. Upload each file whose hash
   differs to `<owner>/<repo>/<path>`. Delete each key in the old manifest
   that is no longer present.
5. Write the new manifest only if every upload and delete succeeded, so a
   failed run is retried in full by the next one. Exit non-zero on any
   failure.

The manifest makes listing the bucket unnecessary, so the credential needs
only `GetObject`, `PutObject` and `DeleteObject` on its prefix.

### The S3 credential: Vault identity token, exchanged at SeaweedFS STS

The repo already does both halves. Nomad jobs swap a JWT for short-lived
SeaweedFS credentials at its STS, one role per job
(`docs/how-to/give-an-aws-sdk-go-service-keyless-seaweedfs-access.md`,
`local.seaweedfs_keyless_jobs` in `deployments/infrastructure/services.tf`).
Workloads mint Vault identity tokens with literal claims, one role each,
readable only by that workload's policy (`vault_identity_oidc_role.openviking_workload`
in `deployments/infrastructure/oidc.tf`). Joined: the caller reads
`identity/oidc/token/<its role>` with its `jwt-github` Vault token, gets a JWT
with audience `seaweedfs` and a literal `ci_repository` claim, and swaps it at
`https://s3.lab.orangecluster.nl` (`AssumeRoleWithWebIdentity`, with
`RoleArn` and `RoleSessionName`) for credentials that last minutes. No S3 key
exists anywhere. What is shown so far: a role pinned to one Nomad job refuses
another (spike:seaweedfs-workload-identity/2), and a key scoped to one bucket
is denied on another (spike:seaweedfs-buckets/1). Rejected: a static IAM user and key per caller in Vault KV,
which works with what SeaweedFS has already been shown to do but is a
long-lived key per repo. Rejected: SeaweedFS STS trusting GitHub's issuer
directly, which would put a second list of who may write outside Vault.

Terraform, all in the infrastructure root, per
`.claude/rules/terraform-file-layout.md`:

- `deployments/infrastructure/variables.tf`: each `var.vault_ci_callers` entry
  gains an optional `ov_sync = bool`. Add an entry for this repo's sync
  workflow on `main`, `lab` Environment.
- `deployments/infrastructure/oidc.tf`: one `vault_identity_oidc_role` per
  `ov_sync` caller on the `identity-tokens` key, `client_id = "seaweedfs"`,
  `ci_repository` set as a literal, TTL 15 minutes, and `seaweedfs` added to
  that key's `allowed_client_ids`.
- `deployments/infrastructure/machine_roles.tf`: one policy per such caller
  reading only its own token path, attached to its `jwt-github` role.
- `deployments/infrastructure/services.tf`: in `local.seaweedfs_iam`, a second
  OIDC provider for Vault's identity issuer, and per caller a role whose trust
  policy pins `ci_repository` by `StringEquals` (not claim mode, for the comma
  reason in that file) and a policy on `arn:aws:s3:::ov-sync/<owner>/<repo>/*`.
  SeaweedFS reads its IAM config only at start, so the apply restarts it.

### This repo's workflow, tests and knowledge

- `new:.github/workflows/openviking-sync.yaml`: on push to `main` under
  `docs/` or `.okf/`, and `workflow_dispatch`, never `pull_request`.
  `permissions: id-token: write, contents: read`, `environment: lab`,
  `timeout-minutes: 5`, and a concurrency group that queues runs rather than
  cancelling them, since two runs racing on the manifest would lose a write.
  Steps: checkout, `./.github/actions/lab-auth`, `./.github/actions/openviking-sync`.
- `new:cli/tests/test_openviking_sync_action.py`: runs `sync.py` against a
  real git repo under `tmp_path` with a stub `aws` on `PATH`, and asserts
  changed-only uploads, deletes, and no manifest write when one upload fails.
  It also extends the `lab-auth` guard: the sync workflow must not trigger on
  `pull_request`, and every SeaweedFS CI policy resource must end in its own
  `<owner>/<repo>/*`.
- Knowledge: a decision record for the bucket and manifest design and the
  token-to-STS credential. Updates to `.okf/components/seaweedfs.md`,
  `.okf/components/vault-identity.md` and `docs/explanation/workload-identity.md`.
  A how-to, `new:docs/how-to/sync-repository-folders-to-the-ov-sync-bucket.md`,
  per `.claude/rules/how-to-skeleton.md`, and the inputs table on the GitHub
  Actions reference page that `ci-tailscale-access` adds.

Outcome: a push to `main` that adds a test page under `docs/` with a unique
marker runs the workflow, which finishes in under 2 minutes without waiting
on OpenViking. Its log shows one upload, the page is at
`s3://ov-sync/JasperHG90/localstack/docs/...` with the marker, and the
manifest holds its hash. A second run with no change uploads and deletes
nothing. A push that deletes the page deletes the object and its manifest
entry. The job's credential is refused a write to another repo's prefix. No
S3, Vault or Tailscale credential is stored in GitHub. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- Per-prefix S3 credentials brokered through Vault. The plan assumes
  SeaweedFS 4.48 STS trusts Vault's identity-token issuer as a second OIDC
  provider beside Nomad, binds a role on a literal custom claim, and enforces
  a policy scoped to an object prefix inside a shared bucket. Earlier spikes
  showed only the Nomad issuer and whole-bucket scope. If prefix
  scope is not enforced, repos can overwrite each other and the shared bucket
  design fails. If the Vault issuer is refused, the credential falls back to
  a static key per caller in Vault KV. Spike question: on SeaweedFS 4.48 with
  `-s3.iam.config` holding the Nomad provider plus a provider for
  `https://vault.lab.orangecluster.nl/v1/identity/oidc` (client `seaweedfs`),
  does a Vault identity token with literal `ci_repository = "a/x"` get
  credentials for role `ci-a-x` and get refused for role `ci-b-y`, and can
  those credentials put, get and delete under `ov-sync/a/x/` while being
  refused put and delete under `ov-sync/b/y/`? Settled by
  spike:ci-openviking-sync/1: locally, with Vault 2.0.3 and SeaweedFS 4.48,
  STS trusted Vault's identity issuer beside a Nomad provider and refused a
  token with another audience. An `a/x` token got `ci-a-x` and was refused
  `ci-b-y` by the `ci_repository` condition. Its credentials put, got and
  deleted under `a/x/` and were denied every operation under `b/y/`,
  `a/xx/`, `a/` and the bucket root. The issuer there was plain http on a
  Docker network, so the first production run still shows the https issuer.
