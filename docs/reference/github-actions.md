---
description: "The lab-auth action: its inputs, outputs, what it exports and what the calling job must set."
stale_after: 2027-02-15
sources:
  - resource: .github/actions/lab-auth/action.yml
  - resource: .github/workflows/lab-auth-check.yaml
  - resource: deployments/infrastructure/machine_roles.tf
  - resource: deployments/infrastructure/variables.tf
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
| `tailscale-client-id` | no | `T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL` | Client ID of the Tailscale federated identity |
| `tailscale-audience` | no | `api.tailscale.com/T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL` | Audience that federated identity expects |

The client ID and audience are not secrets. Tailscale accepts them only with a
GitHub-signed token whose subject matches the federated identity.

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
| `token_policies` | `default` only |

A `var.vault_ci_callers` entry has four fields:

| Field | Example |
| --- | --- |
| `repository` | `JasperHG90/localstack` |
| `ref` | `refs/heads/main` |
| `environment` | `lab` |
| `workflow` | `lab-auth-check.yaml`, a file name under `.github/workflows/` |

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
