# Two-factor auth on Vault logins

A TOTP second factor on the Vault `userpass` login protects every service
that signs people in through Vault. This page says why the factor sits at
the Vault login, and what it leaves uncovered. The commands and the coverage
table are in [Vault login MFA](../reference/vault-login-mfa.md).

## Why the Vault login is the place to do it

Vault is the OIDC provider for humans here, so a person reaches an app by
completing a Vault login first. Six clients are registered with the `lab`
provider (`deployments/infrastructure/oidc.tf`): the smoke client, nomad,
memex, oauth2-proxy (which fronts dash), grafana and ov-dash. A second factor
on the Vault login therefore reaches all six without touching any of them.

## What this does not cover

- **Only the userpass mount is enforced.** Every human who logs in with a
  password is covered, and that is everyone today.
- **The ID token is a no-factor bearer credential while it lives.** Anyone
  holding one for the ov-dash client can trade it on `jwt-lab` without a
  password, a client secret or a passcode, and for the operator the token that
  comes back carries `developer`, which reaches root in a few commands. Vault
  only issues such a token to a login that already met the factor, so the
  window is the ID token's TTL and nothing else: `id_token_ttl = 600` on the
  client in `oidc.tf` is that window, kept to ten minutes for this reason.
- **The root token bypasses it.** That is a token-auth login, not a userpass
  one. Terraform applies keep working and break-glass stays open, which is also
  the hole: this is only as strong as control of that token.
- **Tokens already issued stay valid.** MFA is checked at login. Step-up MFA on
  individual requests is an Enterprise feature.
- **A `developer` can delete the enforcement.** That policy grants `identity/*`,
  so turning this off is one command. Same non-boundary
  [Cluster roles](cluster-roles.md) records for the group. This raises the cost of a stolen password, not of a
  developer acting in bad faith.
- **Nothing records an enrollment or a reset.** No audit device is enabled on
  this cluster, so a `mfa_reset` leaves no trace. That is the weakest point in
  the scheme, because a reset is a full second-factor replacement.
- **`mfa_reset` leaves a gap with no second factor.** It destroys the old
  secret before minting the new one, so a failure in between leaves the entity
  unenrolled. Re-running it recovers, but only while you still hold a Vault
  token.
