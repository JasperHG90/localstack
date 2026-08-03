---
epic = "upgrade"
depends_on = []
priority = 10
summary = "Decide whether Hermes's native secrets: config feature (Bitwarden/1Password/Command Helper backends, no built-in Vault) is worth adopting alongside or instead of our existing Nomad vault{}+template secret injection."
stub = true
---
# Ticket: evaluate-hermes-native-secrets

## Triggered by

Hermes docs (https://hermes-agent.nousresearch.com/docs/user-guide/secrets/)
describe a native secrets-reading feature, discovered while scoping
`U5-upgrade-hermes-bifrost-versions`.

## Vision & rough premises

- P1 (VERIFIED via WebFetch of the docs page): Hermes's native `secrets:`
  config key supports three backends — Bitwarden Secrets Manager,
  1Password (`op://` refs), and a generic Command Helper CLI. Vault and
  AWS Secrets Manager are explicitly NOT built in; the docs say they
  belong in plugin repos.
- P2 (VERIFIED, `deployments/applications/services/hermes.hcl:180-215,
  389-417`): today ALL Hermes secrets (telegram, email, github, nomad
  token, memex auth key, API server key, Bifrost virtual key) come from
  Nomad's `vault {}` stanza + consul-template `template` blocks rendering
  Vault KV2 reads into `local/hermes.env` and `secrets/file.env`. This
  already works, needs no new secret backend, and is orthogonal to
  Hermes's own `secrets:` key.
- P3 (UNVERIFIED): whether a community or official Vault plugin for
  Hermes's `secrets:` system exists. If none exists, adopting the native
  feature for Vault-backed secrets means writing a Command Helper script
  that shells out to `vault kv read`, or not adopting the feature.
- P4 (per docs, VERIFIED): secrets from this feature do not override
  `.env`/shell values by default (`preserve_existing`/`override_existing`
  govern precedence) — so partial adoption alongside the existing flow is
  at least structurally possible, not an all-or-nothing switch.

## Non-goals

- Not migrating Hermes off Vault-backed secrets onto Bitwarden/1Password.
- Not building a Command Helper Vault-CLI script speculatively.

## Open questions

1. Is adopting Hermes's native `secrets:` feature worth it here at all,
   given it has no built-in Vault backend? Recommendation: default to
   NO — keep the existing `vault{}` + `template` injection — unless
   flesh-out finds a concrete win (e.g. secret rotation without a Nomad
   job restart) that offsets writing and maintaining a Command Helper
   script.
2. If adopted for a subset of secrets, which ones benefit most (e.g.
   ones needing manual rotation vs. Terraform-generated ones)?

## Premises / assumptions

See "Vision & rough premises" above — P1-P4.
