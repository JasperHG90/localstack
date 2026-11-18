---
description: "The lab-auth and openviking-sync actions: their inputs, outputs, what they export and what the calling job must set."
stale_after: 2027-02-15
sources:
  - resource: .github/actions/lab-auth/action.yml
  - resource: .github/workflows/lab-auth-check.yaml
  - resource: deployments/infrastructure/machine_roles.tf
  - resource: deployments/infrastructure/variables.tf
  - resource: .github/actions/openviking-sync/action.yml
  - resource: .github/actions/openviking-sync/sync.py
  - resource: .github/workflows/openviking-sync.yaml
  - resource: deployments/infrastructure/oidc.tf
  - resource: deployments/infrastructure/services.tf
---

# GitHub Actions

## Summary

`lab-auth` is a composite action in this repository,
`.github/actions/lab-auth`. A job that calls it joins the lab tailnet as an
ephemeral `tag:ci` node and holds a Vault token that expires within minutes.
Call it by commit SHA:

```yaml
uses: JasperHG90/localstack/.github/actions/lab-auth@<commit-sha>
```

How to set a repository up for it is
[How to authenticate a GitHub workflow to the lab](../how-to/authenticate-a-github-workflow-to-the-lab.md).

## Details

### Inputs

| Input | Required | Default | What it sets |
| --- | --- | --- | --- |
| `vault-role` | yes | none | Vault role on the `jwt-github` mount, a key of `var.vault_ci_callers` |
| `vault-addr` | no | `https://vault.lab.orangecluster.nl` | Vault address the login goes to, exported as `VAULT_ADDR` |
| `vault-mount` | no | `jwt-github` | Path of Vault's JWT auth mount for GitHub tokens |
| `tags` | no | `tag:ci` | Tailscale tags the runner joins with |
| `tailscale-client-id` | no | empty: picked from the job's OIDC subject | Client ID of a Tailscale federated identity |
| `tailscale-audience` | no | empty: `api.tailscale.com/<client ID>` | Audience that federated identity expects |

### Tailscale identities

With `tailscale-client-id` empty, the action reads the `sub` of the job's
GitHub OIDC token and picks one of two federated identities:

| Subject starts with | Repositories | Client ID |
| --- | --- | --- |
| `repo:JasperHG90@8079803/` | created after 2026-07-15 | `T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL` |
| anything else, such as `repo:JasperHG90/` | created before 2026-07-15 | `T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL` |

The client IDs and audiences are not secrets. Tailscale accepts them only with
a GitHub-signed token whose subject matches the identity.

### Outputs and environment

| Output | Environment variable | Value |
| --- | --- | --- |
| `vault-addr` | `VAULT_ADDR` | The `vault-addr` input |
| `vault-token` | `VAULT_TOKEN` | A Vault token, masked in the log |

Both variables are written to `$GITHUB_ENV`, so every later step in the job
sees them.

### What the calling job must set

| Setting | Value | Why |
| --- | --- | --- |
| `permissions` | `id-token: write` | The action requests the job's GitHub OIDC token twice: for Tailscale, and with audience `vault.io` for Vault |
| `environment` | `lab` | The federated identity's subject and the Vault role both require it |
| trigger | not `pull_request` or `pull_request_target` | A fork's code would run with the job's OIDC token. `cli/tests/test_lab_auth_action.py` fails on it in this repository |
| `timeout-minutes` | any | The same test requires one in this repository |

### The Vault role a caller gets

One `vault_jwt_auth_backend_role` per entry in `var.vault_ci_callers`, in
`deployments/infrastructure/machine_roles.tf`:

| Field | Value |
| --- | --- |
| `bound_audiences` | `["vault.io"]` |
| `bound_claims` (exact match) | `repository`, `ref`, `environment`, and `workflow_ref` = `<repository>/.github/workflows/<workflow>@<ref>` |
| `user_claim` | `repository` |
| `token_ttl`, `token_max_ttl` | 300 and 600 seconds |
| `token_policies` | `default`, plus `ci-ov-sync-<key>` when `ov_sync` is true |

A `var.vault_ci_callers` entry has these fields:

| Field | Example |
| --- | --- |
| `repository` | `JasperHG90/localstack` |
| `ref` | `refs/heads/main` |
| `environment` | `lab` |
| `workflow` | `lab-auth-check.yaml`, a file name under `.github/workflows/` |
| `ov_sync` | optional, default `false`; `true` lets the caller use openviking-sync |

### What the runner reaches

The tailnet policy lets `tag:ci` reach `192.168.2.30` on TCP 443, the HAProxy
edge, and nothing else. Every lab name resolves to that address, so
`https://vault.lab.orangecluster.nl`,
`https://openviking-api.lab.orangecluster.nl` and
`https://s3.lab.orangecluster.nl` answer. The routes behind each name are in
[Edge routes](edge-routes.md).

### lab-auth-check

`.github/workflows/lab-auth-check.yaml` runs on `workflow_dispatch` only. It
calls the action, looks up its own Vault token, checks the three names above
answer, and checks that `192.168.2.30:22`, `192.168.2.30:8200`,
`192.168.2.50:1933`, `192.168.2.29:8333` and firebat's tailnet address on 8200
time out. It prints one PASS or FAIL row per check and fails on any FAIL.

## openviking-sync

`.github/actions/openviking-sync` mirrors git-tracked folders into the calling
repository's own `<owner>/<repo>/` prefix of the `ov-sync` bucket, where
`ov-sync-consumer` picks them up. A job runs it after `lab-auth`, whose
`VAULT_ADDR` and `VAULT_TOKEN` it needs. How to set a repository up is
[How to sync repository folders to the ov-sync bucket](../how-to/sync-repository-folders-to-the-ov-sync-bucket.md).

### openviking-sync inputs

| Input | Required | Default | What it sets |
| --- | --- | --- | --- |
| `folders` | no | `docs` and `.okf` | Repo-relative folders to sync, separated by spaces or newlines |
| `bucket` | no | `ov-sync` | The shared bucket |
| `s3-endpoint` | no | `https://s3.lab.orangecluster.nl` | SeaweedFS's S3 and STS endpoint |
| `credential-role` | no | empty: `ci-<the Vault role lab-auth logged in with>` | Name of both the Vault identity-token role and the SeaweedFS role |

The action has no outputs and exports nothing to `$GITHUB_ENV`. Its S3
credentials exist only inside its own step.

### What a run does

| Step | Detail |
| --- | --- |
| Check | Fails unless `VAULT_ADDR` and `VAULT_TOKEN` are set |
| Token | Reads `identity/oidc/token/<credential-role>` from Vault: audience `seaweedfs`, a literal `ci_repository` claim, 15 minutes |
| Credentials | `AssumeRoleWithWebIdentity` at `s3-endpoint` for `arn:aws:iam::role/<credential-role>`; the three values are masked |
| Manifest | Reads `<owner>/<repo>/_state/manifest.json`, a JSON map of repo-relative path to sha256. A missing one (`NoSuchKey`) is empty |
| Upload | Every git-tracked file under `folders` whose sha256 differs, to `<owner>/<repo>/<path>` |
| Delete | Every manifest path no longer tracked |
| Write | The manifest as the bucket now stands: every 50 uploads, so a run the job timeout kills resumes where it stopped, and at the end when something changed. A failed upload keeps its old entry, a failed delete keeps its entry |
| Exit | Non-zero if any upload, delete or the final manifest write failed. A failed write every 50 uploads is reported and does not fail the run |

### What an ov_sync caller gets

| Piece | Name | Scope |
| --- | --- | --- |
| Vault identity-token role | `ci-<key>` | key `identity-tokens`, `client_id` `seaweedfs`, TTL 900 seconds |
| Vault policy | `ci-ov-sync-<key>` | `read` on `identity/oidc/token/ci-<key>` only |
| SeaweedFS role | `ci-<key>` | trusts provider `vault` when `oidc:ci_repository` equals the repository |
| SeaweedFS policy | `ci-<key>` | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `arn:aws:s3:::ov-sync/<owner>/<repo>/*` |

The SeaweedFS `vault` provider's issuer is
`https://vault.lab.orangecluster.nl/v1/identity/oidc`.

### openviking-sync workflow

`.github/workflows/openviking-sync.yaml` runs on a push to `main` that
touches `docs/` or `.okf/`, and on `workflow_dispatch`. It logs in as
`localstack-openviking-sync` and syncs both folders. Its concurrency group,
`openviking-sync`, runs one at a time and never cancels a running one. A
newer queued run replaces an older queued one.
`cli/tests/test_openviking_sync_action.py` fails if it gains a
`pull_request` trigger or loses its environment, permissions, timeout or
one-at-a-time concurrency.
