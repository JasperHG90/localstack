### Nomad UI and `nomad login` sign-in, backed by Vault's `lab` OIDC provider.
###
### Two halves, both Terraform:
###
###   Vault side  — an OIDC client for Nomad, an assignment gating on F11's
###                 `developer` group, and the key registration.
###   Nomad side  — the ACL auth method and its binding rule.
###
### The Nomad half needs a MANAGEMENT token. `nomad/role/deploy` is
### `type = "client"` (nomad_deploy_role.tf:59), which is why an earlier draft
### of this ticket concluded the work had to move to Ansible. It does not:
### `type` is a field on the role, not a ceiling. `vault_nomad_secret_role.manage`
### below mints a management token, and the aliased provider uses it. Measured
### 2026-08-02 against the live cluster; both probe artifacts were torn down.
###
### The DEFAULT `nomad` provider is untouched. It is bare (providers.tf:26) and
### reads NOMAD_TOKEN from the environment, which today is the bootstrap token.
### Once F8 moves this root to a brokered client token, that credential will
### 403 on the two ACL resources here — which is exactly why they sit behind
### the alias rather than the default.

### --- Vault side -------------------------------------------------------------

### Who is allowed in. F11's `developer` group, referenced directly: it lives in
### developer_group.tf in this same root, so no data source is needed.
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

### --- The management credential ----------------------------------------------

### A second Nomad role, distinct from `deploy`, minting a MANAGEMENT token.
###
### `global = true` governs whether the brokered OPERATOR token replicates
### across regions. It is unrelated to the auth method's `token_locality`,
### which governs tokens issued to USERS. One region here, so it is moot; it is
### set so a second region would not silently break this root.
resource "vault_nomad_secret_role" "manage" {
  backend = "nomad"
  role    = "manage"
  type    = "management"
  global  = true
}

### NO depends_on HERE, DELIBERATELY. An earlier revision ordered this read
### after vault_policy.developer, to guarantee the `nomad/creds/manage` grant
### landed first. Measurement killed that idea twice over.
###
### It caused a 403 on the NEXT apply after any edit to the policy. The
### depends_on defers this read to apply time, but Terraform refreshes the
### existing nomad_acl_auth_method BEFORE that, configuring the aliased provider
### from state -- which holds the previous run's token, dead at the 30m lease.
### The trigger is any edit to the policy TEXT: the body is a heredoc, so its
### `#` comments are part of the document Vault stores, and a typo fix arms it.
### Worse, it only fires when more than 30m has passed since the last run, so it
### reads as intermittent.
###
### And the protection was illusory anyway. Measured: with depends_on moved onto
### the role instead, this data source reads at PLAN time -- before the policy
### write happens at apply time. Any arrangement that lets the read happen early
### enough to avoid breaking refresh is also too early to be ordered after a
### policy write. The two are the same mechanism.
###
### So the grant must PRE-EXIST rather than be ordered. Today that is free: this
### root runs as root. Post-F8, if the runner's own token lacks
### `nomad/creds/manage`, this read 403s once; apply the grant first, then
### re-run. One-time, not every policy edit.
###
### THE INVARIANT: a provider fed by a short-TTL brokered credential must
### re-read that credential every run. Anything that defers the read breaks
### refresh.
###
### Two consequences of reading every run, both benign but surprising:
### each plan and apply mints a fresh global management token (`vault read
### nomad/config/lease` reports ttl 30m, max_ttl 1h), and Terraform never
### revokes a data-source lease, so `vault-manage-*` tokens accumulate live
### until they age out within the hour.
data "vault_nomad_access_token" "manage" {
  backend = vault_nomad_secret_role.manage.backend
  role    = vault_nomad_secret_role.manage.role
}

provider "nomad" {
  alias     = "manage"
  secret_id = data.vault_nomad_access_token.manage.secret_id
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
### in oidc.tf.
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
    # this provider advertises `scopes_supported = [groups]` only, so mapping it
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
