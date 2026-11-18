---
description: "Let a workflow in one of your repositories join the tailnet and get a short-lived Vault token through the lab-auth action."
stale_after: 2027-02-15
sources:
  - resource: .github/actions/lab-auth/action.yml
  - resource: deployments/infrastructure/variables.tf
  - resource: deployments/infrastructure/machine_roles.tf
---

# How to authenticate a GitHub workflow to the lab

## Introduction

Give a workflow in one of your GitHub repositories a route to the lab and a
Vault token, with no stored secret. After this, the job's later steps reach
`https://*.lab.orangecluster.nl` and see `VAULT_ADDR` and `VAULT_TOKEN`. Do
this once per workflow file.

## Prerequisites

- A repository owned by `JasperHG90`, and the
  [`gh` CLI](https://cli.github.com/) logged in to it.
- A `localstack login` session ([CLI login](../reference/cli-login.md)),
  because `just apply` in `deployments/infrastructure/` runs
  `localstack env`.

## Directions

### Step 1: Create the lab Environment

In the repository, open **Settings**, then **Environments**, and create an
environment named `lab`. The Tailscale federated identities and the Vault
role all require a job to run in it.

### Step 2: Add the workflow to the caller list

Add an entry to `vault_ci_callers` in
`deployments/infrastructure/variables.tf`. The key is the Vault role name:

```hcl
my-repo-deploy = {
  repository  = "JasperHG90/my-repo"
  ref         = "refs/heads/main"
  environment = "lab"
  workflow    = "deploy.yaml"
}
```

Then apply the root and check the role exists:

```sh
cd deployments/infrastructure && just apply
vault read auth/jwt-github/role/my-repo-deploy
```

The output shows `bound_claims` with all four values.

### Step 3: Call the action from the workflow

In `.github/workflows/deploy.yaml`, set the trigger, permissions,
environment and timeout, then call the action first:

```yaml
on:
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: lab
    timeout-minutes: 15
    steps:
      - uses: JasperHG90/localstack/.github/actions/lab-auth@<commit-sha>
        with:
          vault-role: my-repo-deploy
      - run: curl -sSf -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/auth/token/lookup-self"
```

Pin a commit SHA of `JasperHG90/localstack` from 2026-11-18 or later. Older
commits join only repositories created before 2026-07-15. Never trigger on
`pull_request` or `pull_request_target`, which would run a fork's code with
the job's token.

### Step 4: Run the workflow

```sh
gh workflow run deploy.yaml --repo JasperHG90/my-repo --ref main
gh run watch --repo JasperHG90/my-repo
```

The lab-auth step ends green and the `lookup-self` step prints the token's
details. A run from another branch or workflow file fails at the login with
`Vault refused role my-repo-deploy`.

## Additional resources

- [The `onboard-repo` skill](../../.claude/skills/onboard-repo/SKILL.md):
  ask an agent to "onboard <repo>" and it runs these steps for you.
- [GitHub Actions reference](../reference/github-actions.md): inputs,
  outputs and the Vault role.
- [ADR 0027](../../.okf/decisions/0027-ci-reaches-the-lab-through-a-public-lab-auth-action-and-per-caller-vault-roles.md):
  why the action and the roles are shaped this way.
