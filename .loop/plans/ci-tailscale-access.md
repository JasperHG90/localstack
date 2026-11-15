---
type: plan
title: 'Plan: ci-tailscale-access'
description: A reusable composite GitHub Action, lab-auth, that puts any allowed repository's job on the tailnet as an ephemeral tag:ci node and logs it in to Vault with the job's GitHub OIDC token, the way google-github-actions/auth does for GCP.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:17:15+00:00'
slug: ci-tailscale-access
epic: null
depends_on: []
priority: null
---

# ci-tailscale-access

Relayed from: none

## Intent

Operator answers, 2026-10-20:
- The tailnet policy is Tailscale's default allow-all: one rule, all users
  and devices to all users and devices on all ports (seen in the admin
  console). It is edited only in the Tailscale admin console, which stays the
  master copy; this repo keeps a read-only copy of the rules in
  `.okf/components/tailscale-subnet-router.md`.
- So the build replaces the allow-all rule, in the console, with:
  `autogroup:member` to `*:*` (every person's own devices keep exactly
  today's access), one rule per tag already in use (listed from the admin
  console or API before the change, so no tagged device loses access), and
  `tag:ci` to `192.168.2.30:443` only. Tagged devices match only rules that
  name them, so `tag:ci` gets nothing else.
- Both actions live in this repo.

CI cannot reach the cluster today, and the operator wants any of his
repositories to get in the way a job gets into GCP: one auth step first, then
the steps that use it. This ticket builds that auth step as a reusable
composite action, `lab-auth`. A job that calls it ends up on the tailnet and
holds a short-lived Vault token. `ci-openviking-sync` builds the second action
on top of it.

Why the network part is needed: every lab name resolves publicly to
`192.168.2.30`, a private address, so it works only on the LAN or through the
subnet route firebat advertises to the tailnet (`docs/reference/edge-routes.md`,
`.okf/components/tailscale-subnet-router.md`). Vault
(`vault.lab.orangecluster.nl`) and the OpenViking API
(`openviking-api.lab.orangecluster.nl`) both sit behind HAProxy on
`192.168.2.30:443`, so CI needs that one destination and nothing else.

### Where the action lives

`new:.github/actions/lab-auth/action.yml` in this repository, which is public.
A caller writes `uses: JasperHG90/localstack/.github/actions/lab-auth@<sha>`.
The action sits beside the Terraform and the tailnet policy that decide who it
lets in, so a change to its contract and to the Vault role it logs in to land
in one commit and one review. Rejected: a separate `lab-actions` repository. It
gives cleaner version tags, but splits the action from the roles that enforce
it, and the loop can only build and test in this repository. The cost: tags
here are repository-wide, so callers pin a commit SHA, not a version tag.
Beside it, `new:.github/actions/lab-auth/README.md` holds the usage snippet a
caller sees when browsing the action, and links to the reference page below
for the inputs.

### What the action does

Inputs: `vault-role` (required), `vault-addr` (default
`https://vault.lab.orangecluster.nl`), `vault-mount` (default `jwt-github`),
`tags` (default `tag:ci`), and the Tailscale credential inputs (the client id
for workload identity federation, or an OAuth client id and secret if the
tailnet does not offer federation). Steps:

1. Join the tailnet with the official `tailscale/github-action` as an
   ephemeral node carrying `tags`, passing `--accept-routes`, because
   `tailscale up` on Linux does not accept subnet routes by default.
2. Request the caller job's GitHub OIDC token with audience `vault.io`. A
   composite action runs as steps inside the caller's job, so the token names
   the caller's repository, ref, environment and workflow, not this
   repository. The caller must set `permissions: id-token: write`.
3. Log in at `auth/<vault-mount>/login` with `vault-role`, mask the token, and
   export `VAULT_ADDR` and `VAULT_TOKEN` to `$GITHUB_ENV`, plus the same as
   outputs. Later steps use them as they would after `gcloud auth`.

### Who may log in

The action is public, so anyone can call it. What it can do is decided only by
what the tailnet and Vault accept:

- **Vault, `deployments/infrastructure/machine_roles.tf`** (credentials Vault
  brokers to machines, per `.claude/rules/terraform-file-layout.md`): a JWT
  auth mount `jwt-github` trusting `https://token.actions.githubusercontent.com`,
  and one `vault_jwt_auth_backend_role` per entry in a new caller list,
  `var.vault_ci_callers` in `deployments/infrastructure/variables.tf`, keyed by
  role name. Each entry names an exact `repository`, `ref`, GitHub
  Environment and workflow file. The role binds all four through
  `bound_claims` (`repository`, `ref`, `environment`, `workflow_ref`), with
  `bound_audiences = ["vault.io"]` and a token TTL of minutes. The default list
  holds this repository only. Adding a repository is a reviewed Terraform
  change. Rejected: one role with a glob on `repository_owner`. It would admit
  every repository the owner ever creates without review, and every workflow
  in it. The `environment` and `workflow_ref` bindings are not optional:
  `.github/workflows/claude-ollama.yaml` already holds `id-token: write` and
  runs an agent with tool use on `main` from issue text, so a role bound only
  on repository and ref would accept its token. The roles carry no policy in
  this ticket beyond Vault's default. `ci-openviking-sync` adds the one that
  mints an OpenViking token. The MFA enforcement in
  `deployments/infrastructure/identity.tf` names the userpass accessor only,
  so it does not reach the new mount.
- **Tailnet policy, in the Tailscale admin console, where it lives today.**
  The repository has no ACL file. Add `tagOwners` for `tag:ci` and one grant
  from `tag:ci` to `192.168.2.30:443` and nothing else. Create a credential
  that can only mint ephemeral, pre-approved `tag:ci` nodes: workload identity
  federation bound to the same callers (subject
  `repo:<owner>/<repo>:environment:<env>`) if the tailnet offers it, otherwise
  an OAuth client whose secret each caller holds in its GitHub Environment,
  never as a repository secret. The policy is the only network control. On
  firebat, tailscaled's `ts-input` chain accepts all `tailscale0` traffic
  ahead of ufw, and ufw forwards routed traffic unfiltered
  (`.okf/components/host-firewall.md`).

Rejected: a self-hosted runner on the cluster. The repository is public, and
GitHub warns against self-hosted runners on public repos because a fork's pull
request can run code on them. That would put a code executor on the LAN with
no tailnet policy in front of it. Also rejected: any long-lived Tailscale or
Vault credential readable at repository level, because every workflow can read
those, `.github/workflows/claude-ollama.yaml` included.

### Proving it, and the knowledge

- **Workflow, `new:.github/workflows/lab-auth-check.yaml`**:
  `workflow_dispatch` only, never `pull_request` or `pull_request_target`.
  Explicit `permissions`, the GitHub Environment, a timeout. It calls the
  action by local path, asserts `vault token lookup` works and the edge
  answers, and asserts the ports outside the grant time out. It stays as a
  manual diagnostic.
- **Guard test, `new:cli/tests/test_lab_auth_action.py`**: parses the action
  and the caller list, and fails if a caller role drops the `environment` or
  `workflow_ref` binding, or if a workflow that uses the action triggers on
  `pull_request` or `pull_request_target`.
- **Knowledge**: a decision record (`kmctl new decision`) for the action, its
  home and the per-caller roles. An update to
  `.okf/components/tailscale-subnet-router.md` with the `tag:ci` grant and a
  read-only copy of the policy stanza (the console stays authoritative), and
  to `.okf/components/vault-identity.md` for the new mount. A how-to for a
  repository owner, `new:docs/how-to/authenticate-a-github-workflow-to-the-lab.md`,
  per `.claude/rules/how-to-skeleton.md`, and the inputs table in
  `new:docs/reference/github-actions.md`.

An earlier plan for the network half, C1, is in git at commit 48f52e2 (ticket
C1-cicd-tailscale-github-actions-deploy, since deleted). Its points on GitHub
Environments, `workflow_dispatch` and `tagOwners` carry over. Its dial target
(HAProxy stats on firebat's tailnet address, port 8404) does not: callers need
the lab names, which need the subnet route.

Outcome: a `workflow_dispatch` run of `lab-auth-check` on `main` joins the
tailnet as an ephemeral `tag:ci` node, which is gone from the console after
the run, and gets a Vault token from the GitHub OIDC token alone. From the
runner, `https://vault.lab.orangecluster.nl/v1/sys/health` and
`https://openviking-api.lab.orangecluster.nl/health` answer over the trusted
certificate. `192.168.2.30:8200`, `192.168.2.50:1933` and firebat's tailnet
address on port 8200 time out. A run from a branch other than `main` is
refused at the Vault login. No Tailscale or Vault credential is in a committed
file or a repository-level secret. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- Tailnet policy scope. Tailscale's default policy allows every source to
  reach every destination, and tagged nodes match `*`. If the live policy
  still carries such a rule, a `tag:ci` grant adds nothing and the runner
  reaches every tailnet device and the whole LAN through the subnet route,
  every port on firebat included. Fixing that rewrites access for every
  device on the tailnet, which is a scope change the operator must own, not a
  line added for CI. Spike question: does the live tailnet policy let a node
  tagged `tag:ci` reach anything besides `192.168.2.30:443`? With a grant to
  only that destination, does an ephemeral `tag:ci` node reach
  `https://vault.lab.orangecluster.nl` through the subnet route and time out
  on `192.168.2.30:8200` and firebat's tailnet address?
- Tailscale credential without a stored secret. The plan assumes a caller
  joins with workload identity federation, so no Tailscale secret exists. If
  the tailnet does not offer it, or `tailscale/github-action` cannot use it
  from inside a composite action, every caller must hold an OAuth client
  secret in its own GitHub Environment, and that secret mints `tag:ci` nodes
  from anywhere it leaks. Spike question: does this tailnet offer GitHub
  workload identity federation that mints only ephemeral `tag:ci` nodes,
  bound to a subject such as `repo:JasperHG90/localstack:environment:<env>`,
  and does `tailscale/github-action`, called from a composite action in
  another repository, join with it and refuse a job outside that subject?
- Vault login for callers in other repositories. The plan assumes a composite
  action referenced as `JasperHG90/localstack/.github/actions/lab-auth@<ref>`
  receives the caller job's GitHub OIDC token, and that Vault's JWT mount,
  which must fetch GitHub's keys from the cluster, can bind a role on its
  `repository`, `ref`, `environment` and `workflow_ref` claims. If the token
  names the action's repository instead, or Vault cannot reach GitHub's keys,
  the per-caller roles cannot tell callers apart. Spike question: from a
  second repository whose job declares an Environment and calls the action
  cross-repo, which `repository`, `environment` and `workflow_ref` does the
  token carry? Does a `jwt-github` role bound on those claims accept it, and
  refuse a token from `.github/workflows/claude-ollama.yaml` on `main` and
  from the same workflow on another branch?
