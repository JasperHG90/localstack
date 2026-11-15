---
type: decision
title: "ADR 0027: CI reaches the lab through a public lab-auth action and per-caller Vault roles"
description: "A composite action in this repo joins a job to the tailnet as tag:ci through a Tailscale federated identity and logs it in to Vault with its GitHub OIDC token, and one jwt-github role per allowed workflow decides who gets a token."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-15T22:03:09Z
status: stable
sources:
  - resource: ".github/actions/lab-auth/action.yml"
  - resource: "deployments/infrastructure/machine_roles.tf"
  - resource: "deployments/infrastructure/variables.tf"
---

# ADR 0027: CI reaches the lab through a public lab-auth action and per-caller Vault roles

## Context

CI could not reach the cluster. Every lab name resolves publicly to
`192.168.2.30`, a private address, so a GitHub-hosted runner reaches Vault,
the OpenViking API and SeaweedFS S3 only through the subnet route firebat
advertises to the tailnet ([ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md),
[the subnet router](/components/tailscale-subnet-router.md)). The operator
wanted any of his repositories to get in the way a job gets into GCP: one auth
step, then the steps that use it.

Two facts shaped the choice. This repository is public. And
`.github/workflows/claude-ollama.yaml` already holds `id-token: write` and
runs an agent with tool use on `main` from issue text, so a gate keyed only on
repository and branch would hand its token the lab.

## Decision

A composite action, `.github/actions/lab-auth`, is in this repository. A
caller writes `uses: JasperHG90/localstack/.github/actions/lab-auth@<sha>`. It
joins the job to the tailnet with `tailscale/github-action@v4` through a
Tailscale federated identity (subject `repo:JasperHG90/*:environment:lab`, tag
`tag:ci`), then posts the job's GitHub OIDC token, audience `vault.io`, to
Vault's `jwt-github` mount and exports `VAULT_ADDR` and `VAULT_TOKEN`.

The tailnet policy, saved in the Tailscale admin console, lets `tag:ci` reach
`192.168.2.30:443` and nothing else. Vault decides which repository gets a
token: one `vault_jwt_auth_backend_role` per entry in `var.vault_ci_callers`
(`deployments/infrastructure/machine_roles.tf`), each bound by exact match on
`repository`, `ref`, `environment` and `workflow_ref`, with tokens that live
five minutes and Vault's `default` policy only. Adding a caller is a reviewed
Terraform change.

Rejected:

- **A separate `lab-actions` repository.** It gives clean version tags, but
  splits the action from the roles and policy that decide what it may do, and
  the loop builds and tests in this repository only.
- **One role with a glob on `repository_owner`.** It would admit every
  repository the owner ever creates, and every workflow in each, without
  review.
- **A self-hosted runner on the cluster.** The repository is public, and a
  fork's pull request can run code on a self-hosted runner. That puts a code
  executor on the LAN with no tailnet policy in front of it.
- **A stored Tailscale auth key or Vault token as a repository secret.** Every
  workflow in the repository can read one, `claude-ollama.yaml` included, and
  it does not expire with the job.

## Consequences

- No Tailscale or Vault credential is stored anywhere in GitHub. The client
  ID and audience of the federated identity are action defaults, because they
  are useless without a GitHub-signed token that matches its subject.
- Tags in this repository cover the whole repository, so callers pin a commit
  SHA, not a version tag.
- The federated identity admits any operator repository's `lab` job to the
  tailnet. The network gate is the tailnet policy, not the repository list.
- A repository created after mid-2026 issues GitHub's immutable OIDC subject
  (`repo:JasperHG90@8079803/<repo>@<id>:environment:lab`), which the existing
  subject cannot match. Such a repository needs a second federated identity
  in the Tailscale console, subject `repo:JasperHG90@8079803/*:environment:lab`.
  `docs/how-to/authenticate-a-github-workflow-to-the-lab.md` names that step.
  For the same reason no Vault role binds on `sub`.
- The `lab` GitHub Environment has no branch policy, so Vault's `ref` binding
  is the only branch gate.
- `.github/workflows/lab-auth-check.yaml` is a manual diagnostic, and
  `cli/tests/test_lab_auth_action.py` fails if a role drops a claim or a
  workflow that uses the action gains a `pull_request` trigger.
