### Vault OIDC identity provider — the singleton half.
###
### F2 owns only what is genuinely one per cluster: the signing key, the shared
### scope, the provider itself, and ONE throwaway smoke-test client that proves
### a human can complete a login end to end.
###
### Consumer clients (dash/L1, mlflow/R1, phoenix/R4, the MinIO tiers/M2) are
### NOT created here. Each consumer ticket creates its own
### vault_identity_oidc_client, its own group and assignment, and its own
### vault_identity_oidc_key_allowed_client_id entry pointing at this key.
###
### THE KEY needs no edit here: allowed_client_ids is deliberately NOT set
### inline on it, because the standalone
### vault_identity_oidc_key_allowed_client_id resource lets a consumer register
### itself, and the inline form creates a Terraform cycle with the client's
### `key` reference.
###
### THE PROVIDER is different, and a consumer DOES edit one line of this file.
### Vault gates the provider on its allowed_client_ids list — that list being
### ["*"] is exactly why the built-in `default` provider accepts anything (see
### the provider block below) — and there is no standalone resource for it, as
### there is for the key. So each consumer appends its client to
### `local.oidc_provider_client_ids`. That single marked line is the whole
### contract; nothing else in this file changes.

resource "vault_identity_oidc_key" "lab" {
  name             = "lab"
  algorithm        = "RS256"
  rotation_period  = 86400 # 24h
  verification_ttl = 86400 # 24h; tokens signed by a rotated key stay valid this long
}

### The shared claim contract. Emits the entity's Vault group names as a
### `groups` array, which oauth2-proxy consumes via --oidc-groups-claim.
###
### NOT every relying party reads this claim: M2 tiers MinIO on `role_policy`,
### which bypasses the claim entirely and gates on the per-client assignment
### instead. See plan Q8. Each consumer ticket states which mechanism it uses.
resource "vault_identity_oidc_scope" "groups" {
  name        = "groups"
  description = "Vault group names of the authenticated entity"

  # The placeholder must NOT be quoted, and this must NOT be built with
  # jsonencode. Vault's identity templating emits fully-formed JSON per
  # substitution: for a list it returns `["a","b"]`, brackets included. Wrapping
  # it in quotes yields {"groups": "["a","b"]"}, which is invalid JSON.
  #
  # That failure is SILENT and passes apply. Vault validates the template
  # against a zero-group entity, which renders {"groups": "null"} and parses
  # fine; only at token issuance with real groups does it break, and
  # mergeJSONTemplates then logs a warning and continues with an empty claim
  # set. The token comes back signed and simply has no groups claim.
  template = "{\"groups\":{{identity.entity.groups.names}}}"
}

### Consumer clients permitted to use this provider.
###
### >>> CONSUMER TICKETS: APPEND YOUR CLIENT HERE. <<<
### This is the one line in this file a consumer ticket edits. Vault has no
### standalone resource for a provider's allowed client ids (it has one for the
### key), so the list must be inline. Omitting your client means Vault refuses
### the authorization request against this provider.
locals {
  oidc_provider_client_ids = [
    vault_identity_oidc_client.smoke.client_id,
    vault_identity_oidc_client.nomad.client_id,
  ]
}

### The issuer. issuer_host + https_enabled produce
### https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab.
###
### Consumers must point at THIS provider, never Vault's built-in `default`
### one: `default` advertises allowed_client_ids = ["*"] and an issuer of
### http://<raw-ip>:8200, so a consumer aimed at it would work while silently
### bypassing every scoping decision made here. F2 does not alter `default` —
### it is Vault built-in — but see plan Q9.
resource "vault_identity_oidc_provider" "lab" {
  name               = "lab"
  https_enabled      = true
  issuer_host        = var.vault_issuer_host
  allowed_client_ids = local.oidc_provider_client_ids
  scopes_supported   = [vault_identity_oidc_scope.groups.name]
}

### --- Smoke test -----------------------------------------------------------
### The minimum needed to prove the issuer works: a group, an assignment
### gating on it, and a client. Explicitly throwaway. Once a real consumer
### client exists, this can be deleted — but remove its entry from
### `local.oidc_provider_client_ids` in the same change, or the provider
### references a client id that no longer exists.

resource "vault_identity_group" "smoke" {
  name     = "oidc-smoke"
  type     = "internal"
  policies = []

  member_entity_ids = [vault_identity_entity.operator.id]
}

resource "vault_identity_oidc_assignment" "smoke" {
  name       = "oidc-smoke"
  group_ids  = [vault_identity_group.smoke.id]
  entity_ids = []
}

resource "vault_identity_oidc_client" "smoke" {
  name             = "oidc-smoke"
  key              = vault_identity_oidc_key.lab.name
  redirect_uris    = var.oidc_smoke_redirect_uris
  assignments      = [vault_identity_oidc_assignment.smoke.name]
  client_type      = "confidential"
  id_token_ttl     = 3600
  access_token_ttl = 3600
}

### Registers the smoke client against the key WITHOUT editing the key
### resource. This is the pattern every consumer ticket copies.
resource "vault_identity_oidc_key_allowed_client_id" "smoke" {
  key_name          = vault_identity_oidc_key.lab.name
  allowed_client_id = vault_identity_oidc_client.smoke.client_id
}
