### Vault OIDC identity provider, and every client that uses it.
###
### The singleton half comes first, and F2 owns it: the signing key, the shared
### scopes, the provider itself, and ONE throwaway smoke-test client that proves
### a human can complete a login end to end.
###
### Every consumer client then follows, one section each, and each owns its own
### vault_identity_oidc_client and its own vault_identity_oidc_key_allowed_client_id
### entry pointing at a key. A new consumer adds a section here; it does not add
### a file.
###
### WHETHER IT ALSO CREATES A GROUP AND AN ASSIGNMENT DEPENDS. Four answers to
### "who is allowed in", in the order to try them (docs/cluster-roles.md and
### the "Adding a service" section of docs/vault-human-auth.md carry the same
### list):
###
###   1. Reference an existing tier group, `developer` or `admin`
###      (identity.tf), when one already names who gets in.
###      You still create your own assignment. G2 does this.
###   2. Add an entry to `local.app_user_groups` (identity.tf) when the
###      service needs its own tier. The map ships EMPTY, so this is the branch
###      that keeps app consumers on the scaffold instead of routing around it.
###   3. Neither group nor assignment: set `assignments = ["allow_all"]`, the
###      built-in, when the answer is "anyone who can log in". Four of the six
###      known consumers (G1, R1, R4, L1) declare flat access and want this.
###   4. Create a service-specific group only when none of the three fits.
###
### THE KEY needs no edit here: allowed_client_ids is deliberately NOT set
### inline on it, because the standalone
### vault_identity_oidc_key_allowed_client_id resource lets a consumer register
### itself, and the inline form creates a Terraform cycle with the client's
### `key` reference.
###
### THE PROVIDER is different, and a consumer DOES edit one line below.
### Vault gates the provider on its allowed_client_ids list — that list being
### ["*"] is exactly why the built-in `default` provider accepts anything (see
### the provider block below) — and there is no standalone resource for it, as
### there is for the key. So each consumer appends its client to
### `local.oidc_provider_client_ids`. That single marked line is the whole
### contract; nothing else outside your own section changes.

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

### The email claim contract. Grafana refuses a login whose resolved email is
### empty and offers no setting to disable that check, so Grafana cannot work
### without this scope. Most consumers can: memex and the Nomad client both
### speak OIDC with no proxy and log people in on `groups` alone. R4 (Phoenix)
### is the other that needs it; G1 created it, and R4 consumes it rather than
### declaring a second one.
###
### The placeholder must NOT be quoted, for the same reason the `groups`
### template above must not be. Vault's identity templating emits fully-formed
### JSON per substitution, so a metadata lookup arrives already quoted; adding
### quotes yields {"email":""a@b.com""}. Unlike the `groups` case, this one
### fails LOUDLY at apply, because scope creation validates the template
### against a zero-value entity. Do not "fix" that error by adding quotes.
resource "vault_identity_oidc_scope" "email" {
  name        = "email"
  description = "Email address of the authenticated entity"

  template = "{\"email\":{{identity.entity.metadata.email}}}"
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
    vault_identity_oidc_client.memex.client_id,
    vault_identity_oidc_client.oauth2_proxy.client_id,
    vault_identity_oidc_client.grafana.client_id,
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
  scopes_supported = [
    vault_identity_oidc_scope.groups.name,
    vault_identity_oidc_scope.email.name,
  ]
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

### First consumer of the app-user extension point (identity.tf), which is
### the only way to prove the wiring: there is one client here and its
### assignments are inline below.
###
### CONCAT, never replace. The map ships empty, so a replacement writes
### group_ids = [] and breaks F2's live smoke client.
resource "vault_identity_oidc_assignment" "smoke" {
  name = "oidc-smoke"
  # DO NOT COPY THIS LINE. `all_app_user_group_ids` is every tier, which is
  # right only because this is F2's throwaway proof that the extension point is
  # wired. A real consumer binds its own key:
  #   group_ids = [local.app_user_group_ids["<your-tier>"]]
  group_ids  = concat([vault_identity_group.smoke.id], local.all_app_user_group_ids)
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

### --- G2: Nomad UI and `nomad login` ---------------------------------------
### Nomad UI and `nomad login` sign-in, backed by Vault's `lab` OIDC provider.
###
### Two halves, both Terraform:
###
###   Vault side  — an OIDC client for Nomad, an assignment gating on F11's
###                 `developer` group, and the key registration.
###   Nomad side  — the ACL auth method and its binding rule.
###
### The Nomad half needs a MANAGEMENT token. `nomad/role/deploy` is
### `type = "client"` (machine_roles.tf), which is why an earlier draft
### of this ticket concluded the work had to move to Ansible. It does not:
### `type` is a field on the role, not a ceiling. `vault_nomad_secret_role.manage`
### in machine_roles.tf mints a management token, and the aliased provider uses
### it. Measured
### 2026-08-02 against the live cluster; both probe artifacts were torn down.
###
### The DEFAULT `nomad` provider is untouched. It is bare (providers.tf:26) and
### reads NOMAD_TOKEN from the environment, which today is the bootstrap token.
### Once F8 moves this root to a brokered client token, that credential will
### 403 on the two ACL resources here — which is exactly why they sit behind
### the alias rather than the default.

### --- Vault side -------------------------------------------------------------

### Who is allowed in. F11's `developer` group, referenced directly: it lives in
### identity.tf in this same root, so no data source is needed.
###
### Do NOT create a group here. A second one named `developer` collides on
### Vault's unique name, and a differently-named one admits nobody, because the
### assignment gates on membership and the operator entity is in F11's.
resource "vault_identity_oidc_assignment" "nomad" {
  name       = "nomad"
  group_ids  = [vault_identity_group.developer.id]
  entity_ids = []
}

### Both redirect URIs, and both are needed (R3):
###   - the UI callback, where the browser lands after Vault
###   - the CLI callback, where `nomad login` listens (-oidc-callback-addr,
###     default localhost:4649)
###
### Omitting the CLI one breaks terminal login while the UI keeps working. That
### failure is loud, not silent: an unlisted redirect_uri fails at auth-url
### generation with `unauthorized redirect_uri`.
resource "vault_identity_oidc_client" "nomad" {
  name = "nomad"
  key  = vault_identity_oidc_key.lab.name

  redirect_uris = [
    "https://nomad.lab.orangecluster.nl/ui/settings/tokens",
    "http://localhost:4649/oidc/callback",
  ]

  assignments      = [vault_identity_oidc_assignment.nomad.name]
  client_type      = "confidential"
  id_token_ttl     = 3600
  access_token_ttl = 3600
}

### Registers the client against the key without editing the key resource,
### copying the smoke client's pattern.
resource "vault_identity_oidc_key_allowed_client_id" "nomad" {
  key_name          = vault_identity_oidc_key.lab.name
  allowed_client_id = vault_identity_oidc_client.nomad.client_id
}
### --- Nomad side --------------------------------------------------------------

### The client secret passes by reference and never reaches a host filesystem.
### No `sensitive` marking is needed: both
### vault_identity_oidc_client.client_secret and config.oidc_client_secret are
### already sensitive in the installed providers, so it stays out of plan output.
### It does live in state, which is already true of every other secret here.
###
### Points at the `lab` provider, never Vault's built-in `default`. `default`
### advertises allowed_client_ids = ["*"] and an issuer of http://<raw-ip>:8200,
### so a consumer aimed at it works while bypassing every scoping decision made
### at the top of this file.
resource "nomad_acl_auth_method" "oidc" {
  provider = nomad.manage

  name           = "vault"
  type           = "OIDC"
  token_locality = "global"
  max_token_ttl  = "8h"

  config {
    oidc_discovery_url = "https://${var.vault_issuer_host}/v1/identity/oidc/provider/lab"
    oidc_client_id     = vault_identity_oidc_client.nomad.client_id
    oidc_client_secret = vault_identity_oidc_client.nomad.client_secret
    # ["groups"] only. R1 settled this on 2026-08-01: Nomad adds `openid`
    # itself, so listing it here is redundant. Measured either way, the wire
    # carries `scope=openid groups`.
    oidc_scopes      = [vault_identity_oidc_scope.groups.name]
    oidc_enable_pkce = true

    bound_audiences = [vault_identity_oidc_client.nomad.client_id]
    bound_issuer    = ["https://${var.vault_issuer_host}/v1/identity/oidc/provider/lab"]

    allowed_redirect_uris = vault_identity_oidc_client.nomad.redirect_uris

    # No `claim_mappings`. `preferred_username` is a `profile`-scope claim, and
    # this provider does not advertise `profile`, so mapping it
    # would bind an always-empty value. `token_name_format` is left at its
    # default, which reads neither.
    list_claim_mappings = {
      groups = "groups"
    }
  }
}

### The selector and list_claim_mappings above are ONE decision, not two. The
### selector reads the MAPPED name, not the claim name. HashiCorp's own guide
### maps {"groups": "roles"} and selects on list.roles; this file maps
### {"groups": "groups"} and selects on list.groups. Mix them and the selector
### matches nothing.
###
### That mismatch fails LOUDLY, not silently: measured on Nomad 2.0.4, the login
### returns `400 no role or policy bindings matched` and issues no token.
### acl_endpoint.go carries the guard in both the OIDC and JWT paths. Nothing
### validates the pair at create time, though, so a mismatch applies clean and
### only surfaces at first login.
###
### bind_name references the `developer` Nomad ACL policy BY NAME. Ansible owns
### that policy (bootstrap/roles/nomad_server/tasks/main.yml:182-187). Do not
### author or import it here: a Terraform copy gives one policy two owners, and
### the next `just bootstrap` and the following plan would fight forever.
resource "nomad_acl_binding_rule" "developer" {
  provider = nomad.manage

  description = "g2-nomad-ui"
  auth_method = nomad_acl_auth_method.oidc.name
  selector    = "\"developer\" in list.groups"
  bind_type   = "policy"
  bind_name   = "developer"
}

### --- R6: memex ------------------------------------------------------------
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

### --- L1: oauth2-proxy (landing page gate) ---------------------------------
### Flat access: anyone who completes Vault login is let through. Branch 3 of
### the documented procedure (docs/vault-human-auth.md:282-290) — the built-in
### "allow_all" assignment, no group, no vault_identity_oidc_assignment
### resource. Confidential client: oauth2-proxy holds a real client secret,
### and Vault issues none to a public client (see the ticket's requirement 7a).
###
### The redirect URL is a local, not a literal repeated here and in
### services.tf's templatefile call: Vault rejects a callback whose URL is not
### in redirect_uris with "unauthorized redirect_uri", so the client
### registration and the jobspec's OAUTH2_PROXY_REDIRECT_URL must never drift
### apart.
locals {
  oauth2_proxy_redirect_url = "https://dash.lab.orangecluster.nl/oauth2/callback"
  registry_ui_redirect_url  = "https://registry-ui.lab.orangecluster.nl/oauth2/callback"
}

resource "vault_identity_oidc_client" "oauth2_proxy" {
  name = "oauth2-proxy"
  key  = vault_identity_oidc_key.lab.name

  redirect_uris = [
    local.oauth2_proxy_redirect_url,
    local.registry_ui_redirect_url,
  ]

  assignments      = ["allow_all"]
  client_type      = "confidential"
  id_token_ttl     = 3600
  access_token_ttl = 3600
}

### Registers the client against the key without editing the key resource,
### copying the smoke client's pattern.
resource "vault_identity_oidc_key_allowed_client_id" "oauth2_proxy" {
  key_name          = vault_identity_oidc_key.lab.name
  allowed_client_id = vault_identity_oidc_client.oauth2_proxy.client_id
}

### --- G1: Grafana (native generic OAuth client) -----------------------------
### Grafana speaks OIDC itself, so nothing proxies it. Flat access: branch 3 of
### the documented procedure (docs/vault-human-auth.md:288-292) — the built-in
### "allow_all" assignment, no group and no vault_identity_oidc_assignment.
### Confidential, because Vault issues no secret to a public client.
###
### Copies the smoke and nomad clients, NOT memex: `client_type` and `key` are
### immutable after create, so a public client or a private key here would cost
### a destroy, a new client_id, and an edit everywhere the old one is named.
###
### The redirect URL is a local for the same reason oauth2-proxy's is: Vault
### rejects a callback whose URL is not in redirect_uris, so this registration
### and GF_SERVER_ROOT_URL must never drift apart. Grafana does not take the
### URL as a setting — it derives it from root_url plus the fixed
### /login/generic_oauth path, so the two are wired together only by agreeing.
locals {
  grafana_redirect_url = "https://grafana.lab.orangecluster.nl/login/generic_oauth"
}

resource "vault_identity_oidc_client" "grafana" {
  name = "grafana"
  key  = vault_identity_oidc_key.lab.name

  redirect_uris = [
    local.grafana_redirect_url,
  ]

  assignments      = ["allow_all"]
  client_type      = "confidential"
  id_token_ttl     = 3600
  access_token_ttl = 3600
}

resource "vault_identity_oidc_key_allowed_client_id" "grafana" {
  key_name          = vault_identity_oidc_key.lab.name
  allowed_client_id = vault_identity_oidc_client.grafana.client_id
}
