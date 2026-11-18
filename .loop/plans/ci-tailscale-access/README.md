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
epic: ci-lab-access
depends_on: []
priority: null
---

# ci-tailscale-access

Relayed from: none

## Intent

Operator answers, 2026-11-15:
- The tailnet policy is saved in the Tailscale admin console, which stays the
  master copy. It holds: `tagOwners` `tag:ci` owned by `autogroup:admin`; a
  grant from `autogroup:member` to `*`; a grant from `tag:ci` to
  `192.168.2.30` on `tcp:443`; the default `ssh` rule; and a `tests` block in
  which `tag:ci` accepts `192.168.2.30:443` and is denied `192.168.2.30:22`,
  `192.168.2.30:8200`, `192.168.2.50:1933` and `192.168.2.29:8333`. No other
  tags exist. The build copies it, read-only, into
  `.okf/components/tailscale-subnet-router.md`.
- Workload identity federation exists: one federated identity, subject
  `repo:JasperHG90/*:environment:lab` (every operator repo, `lab` GitHub
  Environment), scope Auth Keys write, tag `tag:ci`. Client ID
  `T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL`, audience
  `api.tailscale.com/T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL`. Neither is secret
  (useless without a GitHub-signed token matching the subject), so both are
  action defaults. Per-repo control stays in Vault, `var.vault_ci_callers`.
- The probe repo `JasperHG90/lab-auth-probe` (private, `lab` Environment)
  exists for the cross-repo test. The operator deletes it when that passes.
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
(`vault.lab.orangecluster.nl`), the OpenViking API
(`openviking-api.lab.orangecluster.nl`) and SeaweedFS S3
(`s3.lab.orangecluster.nl`) are all behind HAProxy on `192.168.2.30:443`, so
CI needs that one destination and nothing else.

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
`tags` (default `tag:ci`), `tailscale-client-id` and `tailscale-audience`
(defaults: the client ID and audience above). No OAuth client fallback and no
per-caller Tailscale secret. The caller sets `permissions: id-token: write`
and `environment: lab`. Steps:

1. Join the tailnet with `tailscale/github-action@v4`, passing its
   `oauth-client-id`, `audience` and `tags` inputs, as an ephemeral node.
   v4 passes `--accept-routes` itself, which the subnet route needs, so the
   action leaves `args` empty; passing it again fails
   (spike:ci-tailscale-access/3).
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
  gets its S3 credential. The MFA enforcement in
  `deployments/infrastructure/identity.tf` names the userpass accessor only,
  so it does not reach the new mount.
- **Tailnet policy and federated identity, in the Tailscale admin console.**
  Both are done (above). The policy is the only network control. On
  firebat, tailscaled's `ts-input` chain accepts all `tailscale0` traffic
  ahead of ufw, and ufw forwards routed traffic unfiltered
  (`.okf/components/host-firewall.md`). The federated identity admits any
  operator repo's `lab` job onto the tailnet, so Vault, not Tailscale,
  decides which repo gets a token.

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
  and S3 edges answer, and asserts the ports outside the grant time out. It stays as a
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
`https://openviking-api.lab.orangecluster.nl/health` and
`https://s3.lab.orangecluster.nl` answer over the trusted certificate.
`192.168.2.30:22`, `192.168.2.30:8200`, `192.168.2.50:1933`,
`192.168.2.29:8333` and firebat's tailnet address on port 8200 time out. A run from a branch other than `main` is
refused at the Vault login. No Tailscale or Vault credential is in a committed
file or a repository-level secret. `just pre_commit` and
`uv run --directory cli pytest` pass.

### Delivery: how the outcome is reached

The loop lands on local `main`; the outcome runs on GitHub against the live
Vault. After the ticket lands, in this order:

1. The builder runs `terraform plan` of `deployments/infrastructure` with
   the prod tfvars file and hands the operator the list of
   changes, which must all be this ticket's (the `jwt-github` mount, its
   roles and policies).
2. The operator applies it.
3. The operator pushes local `main` to `origin`. Local `main` is many
   commits ahead of `origin/main`, so this publishes all of them on the
   public repo; that is the operator's call.
4. The builder runs `gh workflow run lab-auth-check.yaml --ref main` and
   watches it pass, then dispatches it from a throwaway branch, sees the
   Vault login refused, and deletes the branch.

The `lab` GitHub Environment already exists on the repo with no branch
policy, so Vault's `ref` binding is the only branch gate, as the plan
intends (Tailscale admits, Vault decides).

## Could invalidate this plan

- Live tailnet reach. The saved policy's `tests` block passes in the console,
  so the rules say what the plan needs. Not yet shown: that an ephemeral
  `tag:ci` node, joined through the subnet route, behaves the same. If it
  reaches more, the runner is on the LAN with ports open and the policy must
  change first. Spike question: does an ephemeral `tag:ci` node joined with
  `--accept-routes` reach `https://vault.lab.orangecluster.nl`,
  `https://openviking-api.lab.orangecluster.nl` and
  `https://s3.lab.orangecluster.nl`, and time out on `192.168.2.30:22`,
  `192.168.2.30:8200`, `192.168.2.50:1933`, `192.168.2.29:8333` and
  firebat's tailnet address on 8200? spike:ci-tailscale-access/4 could not
  answer it (the join failed). Settled by spike:ci-tailscale-access/6: a
  `lab` job in this repo, joined as `tag:ci`, reached Vault (200),
  OpenViking (200) and S3 (403, reachable) on 443, and timed out on all five
  closed targets, firebat's tailnet address on 8200 included.
- Federated join from a composite action in another repo. The federated
  identity exists, so no Tailscale secret is needed, if
  `tailscale/github-action@v4` can use it from inside a composite action
  called cross-repo. If it cannot, every caller needs a stored Tailscale
  secret, which the plan rejects. Spike question: from a `lab`-Environment
  job in `JasperHG90/lab-auth-probe` that calls a composite action in this
  repo by `uses: JasperHG90/localstack/...@<branch>`, does the
  `tailscale/github-action@v4` step join with `oauth-client-id`, `audience`
  and `tags` only, and does a job without `environment: lab` fail to join?
  Not settled: in spike:ci-tailscale-access/3 both jobs, with and without
  the environment, got a 403 at Tailscale's token exchange. The likely
  cause is the federated identity's subject, `repo:JasperHG90/*:environment:lab`,
  which cannot match GitHub's immutable-ID `sub`
  (`repo:JasperHG90@8079803/lab-auth-probe@1459171707:environment:lab`).
  The same run showed v4 adds `--accept-routes` itself, so the action leaves
  `args` empty. Settled for this repo by spike:ci-tailscale-access/5: from
  a `lab` job in localstack, calling the composite action by its remote ref
  (`JasperHG90/localstack/.github/actions/join@<branch>`), v4 joined with
  only the client id, audience and tag, and a job without the environment
  got 403 at the token exchange. localstack issues the legacy subject,
  which the federated identity matches. A caller repo created after
  mid-2026 issues the immutable subject and needs its own federated
  identity (subject `repo:JasperHG90@8079803/*:environment:lab`) in the
  Tailscale console; the how-to names that step, and it is outside this
  ticket's outcome, which runs from this repo.
- Vault login for callers in other repos. The plan assumes the composite
  action gets the caller job's GitHub OIDC token, and that the `jwt-github`
  mount, which fetches GitHub's keys from the cluster, can bind a role on
  `repository`, `ref`, `environment` and `workflow_ref`. If the token names
  this repo instead, or Vault cannot reach GitHub's keys, the per-caller
  roles cannot tell callers apart. Spike question: from
  `JasperHG90/lab-auth-probe` calling the action cross-repo, which
  `repository`, `ref`, `environment` and `workflow_ref` does the token carry?
  Does a `jwt-github` role bound on those claims accept it, and refuse a
  token from `.github/workflows/claude-ollama.yaml` on `main` and from the
  probe workflow on another branch? Settled by spike:ci-tailscale-access/2
  for the claims and the binding: real tokens from five probe jobs carry the
  caller's `repository`, `ref`, `environment` and `workflow_ref`, and a local
  Vault 1.21.1 role bound on all four accepted only the probe workflow on
  `main` in `lab`, refusing another workflow, another branch and both jobs
  without the environment. Two parts are left to the build, not to a spike:
  the action sat in the probe repo, so the build rechecks `workflow_ref`
  when it calls the real action cross-repo, and the cluster's own reach to
  GitHub's keys is shown by the first `lab-auth-check` login. The token's
  `sub` uses GitHub's immutable-ID form
  (`repo:JasperHG90@8079803/lab-auth-probe@1459171707:environment:lab`), so
  no role binds on `sub`.
