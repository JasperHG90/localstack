# lab-auth

Puts the calling job on the lab tailnet as an ephemeral `tag:ci` node and logs
it in to Vault with the job's GitHub OIDC token. Later steps see `VAULT_ADDR`
and `VAULT_TOKEN`. No secret is stored in GitHub.

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

The Vault login works only for a workflow listed in `var.vault_ci_callers` in
`deployments/infrastructure/variables.tf`. Inputs, outputs and the role a
caller gets: [GitHub Actions reference](../../../docs/reference/github-actions.md).
Setting a repository up:
[How to authenticate a GitHub workflow to the lab](../../../docs/how-to/authenticate-a-github-workflow-to-the-lab.md).
