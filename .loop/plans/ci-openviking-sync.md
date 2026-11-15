---
type: plan
title: 'Plan: ci-openviking-sync'
description: A second reusable composite GitHub Action, openviking-sync, that runs after lab-auth, mints an OpenViking token from Vault and syncs chosen folders with ovsync, and a workflow that uses both to sync docs/ and .okf/ on push to main.
slug: ci-openviking-sync
status: draft
depends_on:
- ci-tailscale-access
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:18:40+00:00'
---

# ci-openviking-sync

Relayed from: none

## Intent

Operator answers, 2026-10-20:
- The OpenViking user and account a caller writes as are fixed per calling
  repo in Vault (the caller list in Terraform), not chosen by the workflow,
  so no repo can write as another user.
- The sync mirrors the folders with deletions on: a page removed from
  `docs/` or `.okf/` is removed from OpenViking.
- The action lives in this repo, next to `lab-auth`.

`ci-tailscale-access` builds `lab-auth`, the action that puts a caller's job on
the tailnet with a Vault token in `VAULT_ADDR` and `VAULT_TOKEN`. This ticket
builds the second action, `openviking-sync`, which a job runs after it, the way
a GCP step runs after `gcloud auth`. It syncs folders into OpenViking. This
repository then uses both to keep `docs/` and `.okf/` in OpenViking on every
push to `main`.

### The tool: ovsync

`ovsync` is the `ov-sync` package in `JasperHG90/openviking_extensions`
(`packages/ov-sync`, tag `ov-sync-v0.2.0`, the repo this one already installs
`ov-postgres` and `ov-ext` from in
`deployments/applications/services/openviking/Dockerfile.openviking`). It
installs with
`uv tool install ov-sync --from "git+https://github.com/JasperHG90/openviking_extensions@ov-sync-v0.2.0#subdirectory=packages/ov-sync"`.
What it does, read from its README and source:

- **One way, one folder to one root.** `ovsync run <folder>` writes each file
  to `<root_uri>/<relative path>`. The target URI is the key, so sending a file
  again replaces it rather than adding a copy. Writes go through
  `content/batch-write`, at most 256 files or 16 MB a batch, 8 MB a file. The
  root must exist, and `--create-root` makes it.
- **Auth.** It sends `Authorization: Bearer <api_key>`, plus
  `X-OpenViking-Account` and `X-OpenViking-User` when set. `OV_SYNC_URL`,
  `OV_SYNC_API_KEY`, `OV_SYNC_ACCOUNT` and `OV_SYNC_USER` override the `ov` CLI
  config file. This server runs `auth_mode: oidc` and takes account and user
  from the claims of a Vault-signed JWT sent as Bearer
  (`docs/explanation/openviking-identity.md`), so the Vault identity token is
  the API key and the two header variables stay unset.
- **Settings.** `ov-sync.toml` in the folder, each key overridable by
  `OV_SYNC_<TABLE>__<KEY>`, for example `OV_SYNC_SYNC__ROOT_URI`.
  `include_extensions` (default `.md`, `.txt`, `.csv`, `.json`, `.yaml`,
  `.yml`, `.toml`, `.html`, `.pdf`), exclude globs, exact folder names, and a
  front-matter `ov: skip` that keeps a page out.
- **Updates and deletions.** It records what it sent in `.ov-sync.db`, a
  SQLite file in the folder root, keyed on the relative path with size, mtime
  and a content hash. A file whose bytes match is not sent again, which
  matters because every write re-embeds the file. A deleted file is only
  reported, unless `--delete`, which first commits an OpenViking snapshot and
  deletes nothing if the snapshot fails (`--no-snapshot` skips it). Deletions
  are found only from that file. A fresh runner has none, so without it every
  run sends everything and no run ever deletes.

### The action

`new:.github/actions/openviking-sync/action.yml`, beside the `lab-auth` action
and for the same reason. Callers pin
`JasperHG90/localstack/.github/actions/openviking-sync@<sha>`. A short
`new:.github/actions/openviking-sync/README.md` holds the usage snippet.
Inputs, all with defaults except the role:

| Input | Default | Meaning |
|---|---|---|
| `identity-role` | required | the Vault identity-token role to mint from |
| `folders` | `docs` and `.okf`, one per line | folders to sync |
| `target` | `viking://user/jasper/resources/projects/<repository name>` | root; each folder lands at `<target>/<folder>` |
| `openviking-url` | `https://openviking-api.lab.orangecluster.nl` | server |
| `delete` | `true` | pass `--delete`, so the copy mirrors the folder |
| `include-extensions`, `exclude` | ovsync's defaults | passed as `OV_SYNC_SYNC__*` |
| `ov-sync-ref` | `ov-sync-v0.2.0` | the pinned tag |

Steps: fail early unless `VAULT_ADDR` and `VAULT_TOKEN` are set. Install
`ovsync` at the pinned tag. Read `identity/oidc/token/<identity-role>` with the
Vault token and mask the result. Then, per folder: restore that folder's
`.ov-sync.db` from `actions/cache`, keyed on repository, target and folder, so
a run sends only what changed and sees what was deleted. Run
`ovsync run <folder> --create-root`, with `--delete` when asked. Save the state
file, and fail the step if a batch failed. A cache miss is safe: that run sends
everything again and leaves deletions for the next one.

**User and account are set in Vault, not by the caller.** The `target`
(location) is the caller's to choose. Who the job writes as is fixed by the
identity-token role, and a caller can read only its own role. If the user were
an input, any caller could write into any person's tree.

### What changes in Terraform

- **`deployments/infrastructure/variables.tf`**: each entry in
  `var.vault_ci_callers` (added by `ci-tailscale-access`) gains an optional
  `openviking = { account, user }`. Add an entry for this repository's sync
  workflow, `lab`/`jasper`, bound to the sync workflow below
  on `main`.
- **`deployments/infrastructure/oidc.tf`**: one `vault_identity_oidc_role` per
  caller that has `openviking`, on the `identity-tokens` key, audience
  `openviking`, with `ov_account` and `ov_user` as literals, as
  `vault_identity_oidc_role.openviking_workload` does, because the JWT mount
  owns the entities it creates. TTL one hour, longer than the job's timeout,
  since `ovsync` holds one token for the whole run.
- **`deployments/infrastructure/machine_roles.tf`**: one policy per such
  caller that reads only its own identity-token path, following
  `vault_policy.openviking_workload`, added to that caller's `jwt-github`
  role.

### This repository's workflow and the knowledge

- **`new:.github/workflows/openviking-sync.yaml`**: runs on push to `main`
  under `docs/` or `.okf/`, and on `workflow_dispatch`, never on
  `pull_request`. `permissions: id-token: write, contents: read`, the GitHub
  Environment, a timeout, and a concurrency group that queues runs rather than
  cancelling them. Steps: checkout, `./.github/actions/lab-auth`,
  `./.github/actions/openviking-sync` with its defaults. Today that is 172
  files, 2.4 MB (`docs/` 1.6 MB, `.okf/` 772 KB).
- **Guard test**: extend the `lab-auth` guard test so it also fails when the
  sync workflow triggers on `pull_request` or when an identity-token policy
  grants a wildcard path.
- **Knowledge**: a decision record for the CI identity and the "user is set in
  Vault" choice. Updates to `.okf/components/vault-identity.md`,
  `.okf/components/openviking-service.md`, `docs/reference/openviking.md` and
  the "What is not configured" section of
  `docs/explanation/openviking-identity.md`. A how-to for a repository owner,
  `new:docs/how-to/sync-repository-folders-to-openviking.md`, per
  `.claude/rules/how-to-skeleton.md`, and the inputs table on the GitHub
  Actions reference page `ci-tailscale-access` adds.

Outcome: a push to `main` that adds a test page under `docs/` with a unique
marker string runs the workflow. The Vault login uses only the GitHub OIDC
token, and no Vault or OpenViking credential is stored in GitHub. The page
lands at `viking://user/jasper/resources/projects/localstack/docs/...`, and an OpenViking search for
the marker as `lab`/`jasper` returns it. `.okf/` lands beside it. A second run
with no change sends nothing. A push that deletes the test page removes it from
OpenViking. A `workflow_dispatch` from a branch other than `main` is refused at
the Vault login. `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- ovsync against this server with a Vault token. The plan assumes `ovsync`
  works unchanged against the deployed OpenViking when its API key is a
  Vault identity token, with no account or user headers, and that a user
  with role USER may create a root, batch-write, delete, and commit the
  snapshot `--delete` takes first. If the server refuses any of these, the
  action needs a change in `ov-sync` (another repository) or must drop
  deletion, and the copy stops being a mirror. Spike question: against
  `ghcr.io/jasperhg90/openviking:v0.4.17.1-9` in `auth_mode: oidc`, with a
  Vault identity token whose claims are literal `lab`/`jasper` as the
  `OV_SYNC_API_KEY`, does `ovsync` at `ov-sync-v0.2.0` create
  `viking://user/jasper/resources/projects/<test>`, sync a folder of Markdown, send nothing on a
  second run from a fresh clone with the state file restored, and with
  `--delete` commit a snapshot and remove a deleted file? Does a search as
  `lab`/`jasper` find a synced page, and how long does a first sync of
  `docs/` take?
