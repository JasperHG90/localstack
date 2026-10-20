---
description: The just recipes that enroll and reset a TOTP second factor on Vault logins, and which sign-in surfaces that factor covers.
stale_after: 2027-01-19
sources:
  - resource: scripts/vault_mfa.sh
  - resource: justfile
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/infrastructure/oidc.tf
  - resource: deployments/infrastructure/services/grafana.hcl
---

# Vault login MFA

The commands that manage the TOTP second factor on the Vault `userpass`
login, and which sign-in surfaces the factor reaches. Why it is on the
Vault login is [Two-factor auth on Vault logins](../explanation/vault-login-mfa.md).

## Running it

| Command | Does |
| --- | --- |
| `just mfa_status` | Shows the method, the enforcements, and who logs in through userpass |
| `just mfa_enroll <username>` | Writes that person's QR to `tmp/`, then asks for a code to confirm the scan. Refuses if they already have a secret |
| `just mfa_reset <username>` | Destroys the old secret and issues a new QR. For a lost phone |

All three call `scripts/vault_mfa.sh`, which holds the traps in comments. The
QR lands in `tmp/`, which the repo gitignores. It carries the seed in full, so
it stays a secret until it is scanned and deleted.

Terraform owns the method and the enforcement. The script owns only the
per-person secret, and Terraform must never hold that: the secret is the second
factor, so putting it in state files both factors in one place.

## What a second factor on the Vault login actually reaches

Covered, because they redirect to the `lab` provider and the prompt happens at
Vault: nomad, memex, dash, registry-ui (it reuses the `oauth2_proxy` client),
Grafana's Vault sign-in button, the Hermes dashboard and ov-dash. The factor is
asked once per VAULT session, not once per app, so every SSO redirect after
that passes on the browser's existing Vault session.

Two surfaces never touch that login path, so no enforcement here reaches
them:

| Surface | Credential | Why it is missed |
| --- | --- | --- |
| Grafana | `GF_SECURITY_ADMIN_USER = "admin"` plus a KV password | The local login form is not disabled. `GF_AUTH_DISABLE_LOGIN_FORM` appears nowhere in `deployments/infrastructure/services/grafana.hcl` |
| Vault | the root token | Token auth, not userpass |

Grafana's password is not reachable without an MFA-protected Vault login
today, because it is in KV. It is still a standing shared credential, so one
leak is a permanent bypass that a second factor cannot take back. Closing it
is separate work: disable Grafana's login form.

### ov-dash is covered, and not by answering a challenge

ov-dash sends people to Vault's provider page, so the factor is asked there and
the dashboard never handles one. The ID token it gets back is traded for a
Vault token on `jwt-lab`, the mount the enforcement deliberately leaves out.
