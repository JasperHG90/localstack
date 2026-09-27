# How to sign in to Grafana

## Introduction

Grafana is the authenticated front door to Prometheus, Loki and Tempo. Its
login is Vault SSO, so a Vault login gets you in.

## Prerequisites

- A Vault account you can log in with.
- An `email` on your Vault entity. Step 1 says why.

## Directions

### Step 1: Sign in with Vault

Go to `https://grafana.lab.orangecluster.nl` and press **Sign in with Vault**.
Grafana speaks OIDC itself, so there is no proxy in front of it: it redirects
to Vault's `lab` provider, and you come back as an Editor. Every user who
completes a Vault login gets in, and gets the same role.

Two behaviors are worth knowing before you meet them.

**The first attempt can fail if your browser holds no Vault session.** Vault's
authorization endpoint is a UI path, so a cold browser can bounce with a
generic "Failed to sign in with SSO". Log in to the Vault UI, then retry.
If the retry also fails, stop retrying: the Grafana client admits anyone who
completes a Vault login, so a repeated failure is a configuration or claim
fault, not a permission one. The likeliest cause is a missing `email` on your
Vault entity.

**Your Vault entity needs an `email`.** Grafana refuses a login whose email is
empty and offers no setting to turn that off. The operator entity carries one
(`vault_operator_email` in `deployments/infrastructure/variables.tf`), and any
entity added later needs the same metadata key or its owner cannot sign in.

## Additional resources

- [How to sign in to Grafana without Vault](sign-in-to-grafana-without-vault.md)
- [Monitoring stack reference](../reference/monitoring.md)
