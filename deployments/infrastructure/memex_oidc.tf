### Human SSO into memex through the Vault `lab` OIDC provider.
###
### memex verifies the ID TOKEN here, not the access token. Vault issues an
### opaque batch token as its access_token and signs only the id_token, so the
### client sets `credential: id_token` and this client's `audience` on the
### memex server is the CLIENT ID: an id_token's `aud` carries the client id,
### not a service name. That is the one shape difference from R5's workload
### provider, whose `aud` is the literal `memex`.
###
### Two tiers, both named by one assignment: `app-memex-admins` and
### `app-memex-readers`. The break-glass `admin` group is deliberately NOT
### used — its membership is a `vault write` no apply reverts, so daily memex
### use would mean living in break-glass.

### A DEDICATED signing key, and the reason a 30-day session is possible.
###
### A client's id_token_ttl may not exceed the verification_ttl of THE KEY IT
### REFERENCES, and `key` is a per-client field. The shared `lab` key rotates
### every 24h, which would cap humans at a daily login. This key is memex's
### alone, so lengthening it touches no other consumer.
###
### Vault refuses a verification_ttl over 10x the rotation_period, and a
### rotation_period under a minute. 30d is 4.3x 7d, so this passes.
###
### It also gives memex its own revocation lever: dropping this client from
### `local.oidc_provider_client_ids` unpublishes this whole key ring from the
### provider's JWKS and kills every outstanding memex human token at once,
### touching nothing else. Rotating the key does NOT do that — rotation stamps
### an expiry on the current signing key only, so it revokes just the tokens
### issued since the last rotation.
resource "vault_identity_oidc_key" "memex_human" {
  name             = "memex-human"
  algorithm        = "RS256"
  rotation_period  = 604800  # 7d
  verification_ttl = 2592000 # 30d; caps the client's id_token_ttl below
}

### Who may log in. Both tiers, so a reader can be tested without an admin.
### Spelled out key by key on purpose: `local.all_app_user_group_ids` would
### admit every app tier in the cluster, including other services'.
resource "vault_identity_oidc_assignment" "memex" {
  name = "memex"

  group_ids = [
    local.app_user_group_ids["app-memex-admins"],
    local.app_user_group_ids["app-memex-readers"],
  ]
  entity_ids = []
}

### The client. PUBLIC, because a CLI on a laptop cannot hold a secret; Vault
### advertises `none` in token_endpoint_auth_methods_supported and requires
### PKCE for a public client at both ends.
###
### `client_type` and `key` are both IMMUTABLE after create. Getting either
### wrong costs a destroy + recreate, a new client_id, and a matching edit to
### the server's `audience`.
###
### Both TTLs are 30 days, and access_token_ttl is NOT an oversight. Vault
### returns access_token_ttl as `expires_in`, and the memex client caches
### min(now + expires_in, id_token exp). A short access_token_ttl would
### therefore discard the 30-day id_token after an hour and fall back to the
### API key with every request still returning 200 — silent, and exactly the
### failure this ticket exists to remove.
###
### The redirect port is arbitrary and never matched: memex binds an ephemeral
### loopback port, and Vault strips the port from both sides when the host is
### loopback, comparing scheme, host literal and path exactly. memex sends
### 127.0.0.1; the localhost entry costs nothing and covers a future client.
resource "vault_identity_oidc_client" "memex" {
  name = "memex"
  key  = vault_identity_oidc_key.memex_human.name

  redirect_uris = [
    "http://127.0.0.1:8250/callback",
    "http://localhost:8250/callback",
  ]

  assignments      = [vault_identity_oidc_assignment.memex.name]
  client_type      = "public"
  id_token_ttl     = 2592000 # 30d; must be <= the key's verification_ttl
  access_token_ttl = 2592000 # 30d; see the comment above before shortening
}

### Registers the client against ITS OWN key, not `lab`. Without this the
### browser redirect succeeds and the TOKEN endpoint fails with
### `invalid_client: client is not authorized to use the key` — after the
### redirect, so a read-only authorize probe cannot catch it.
resource "vault_identity_oidc_key_allowed_client_id" "memex" {
  key_name          = vault_identity_oidc_key.memex_human.name
  allowed_client_id = vault_identity_oidc_client.memex.client_id
}
