---
type: proposal
title: Two-factor auth on Vault logins, the handoff
description: "Built and tested but not applied as of 2026-09-12: TOTP on the userpass mount, localstack login speaking Login MFA, and the ov-dash jwt-lab chain that lets the enforcement name the mount. Holds the Terraform inventory and the next steps."
tags: [vault, mfa, ov-dash, handoff]
status: draft
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: vault-2fa
    resource: git:3ec5d1e:docs/vault-2fa.md
    last_modified: 2026-09-12
---

# Two-factor auth on Vault logins, the handoff

Handoff, updated 2026-09-12. Ready to apply, mount-wide. The enrollment
tooling is built and tested, `localstack login` speaks Login MFA, and the
Terraform is in `deployments/infrastructure/identity.tf`. What is left is to
apply it in the order in
`docs/how-to/roll-out-vault-login-mfa.md`, because enforcing before a person holds a secret
locks that account out of userpass.

ov-dash was the one service an enforced mount would have broken. It now signs
people in at Vault's own page rather than through a password form of its own,
so the factor is asked where Vault asks it and the dashboard never sees a
password. The `jwt-lab` section of `identity.tf` carries the mechanism.

The rollout itself is `docs/how-to/roll-out-vault-login-mfa.md`. Why the
enforcement names the mount is
[ADR 0011](/decisions/0011-login-mfa-enforcement-names-the-userpass-mount.md).

## The Terraform

Two resources for the factor itself, in
`deployments/infrastructure/identity.tf` beside `vault_auth_backend.userpass`,
because human auth backends live in that file: `vault_identity_mfa_totp.lab`
and `vault_identity_mfa_login_enforcement.userpass`. The comment above the
second records why it names the accessor rather than an entity.

The ov-dash chain is what lets the enforcement name the mount at all, and it is
four more places:

| Where | What |
|---|---|
| `identity.tf`, `jwt-lab` section | the `jwt` mount, the `ov-dash` role, and one entity alias per person |
| `oidc.tf`, ov-dash section | the `openviking` scope, the assignment, the client, and its key registration |
| `secrets.tf` | the client id and secret, published to `default/ov-dash/oidc` |
| `applications/services.tf` and `services/ov-dash.hcl` | `AUTH_MODE=vault-oidc`, the issuer, the mount and role names, and the templates that read the client credentials |

None of it has been applied. `terraform validate` and `terraform fmt` pass.
`terraform plan` runs from the devcontainer once `eval "$(localstack env)"` has
put a live token in the environment; an earlier note here said the Consul token
lacked `key:read` on `terraform/infrastructure`, and that is no longer true.

## Next steps

1. Apply in the order in
   `docs/how-to/roll-out-vault-login-mfa.md`, and confirm `localstack login` prompts for a
   passcode. That is the first time this runs against real Vault: the MFA
   exchange is covered by tests against a fake one, not by a live login.
2. Sign in to ov-dash through the provider page and read `/api/session`. The
   chain has three hops, and only the first is proven by a prompt appearing:
   the trade on `jwt-lab` and the mint can each fail with a token that looks
   fine until OpenViking answers 401.
3. Consider an audit device, so an enrollment or a reset is recorded. That gap
   is older and wider than this work.

## Key references

- `deployments/infrastructure/identity.tf`: the two MFA resources, and the
  `jwt-lab` mount, role and aliases the ov-dash chain needs.
- `deployments/applications/services/ov-dash.hcl`: the dashboard's own
  settings, and what each one is for.
- `deployments/infrastructure/oidc.tf`: the six clients this covers, ov-dash
  among them.
- `scripts/vault_mfa.sh`: enrollment, reset, status, and the traps.
- `scripts/vault_mfa_test.sh`: `just mfa_test`, a fake-Vault suite that needs
  no cluster.
- `justfile`: the three `mfa_*` recipes.
- `docs/reference/vault-human-auth.md`: the login flow this adds a factor to.
- `cli/src/localstack_cli/auth/vault.py`: `MFARequired` and `validate_mfa`.
- `docs/explanation/cluster-roles.md`: what `developer` and `admin` can
  already reach.
