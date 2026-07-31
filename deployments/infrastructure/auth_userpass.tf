### Human auth backend.
###
### Before this, `vault auth list` held only jwt-nomad/ (workload identity) and
### token/. There was no way for a human to obtain an entity-bearing token, so
### nothing entity-gated — including this ticket's own OIDC assignment — could
### be exercised at all. The harness VAULT_TOKEN is root and reports
### entity_id: "", which is why a root token cannot stand in for this.
###
### Kept in its own file, separate from oidc.tf: a later ticket may move human
### auth to a federated backend (Google was considered and deferred) without
### touching the OIDC stack.

resource "vault_auth_backend" "userpass" {
  type        = "userpass"
  path        = "userpass"
  description = "Human logins. Entities created here are what OIDC assignments gate on."
}

resource "random_password" "operator" {
  length  = 32
  special = false
}

### No dedicated userpass-user resource exists in the pinned provider 5.3.0,
### so the user is written through the generic endpoint. token_policies is
### deliberately empty: this account exists to obtain an identity, not
### standing privilege. Grant policies per group as real needs appear.
resource "vault_generic_endpoint" "operator" {
  path                 = "auth/${vault_auth_backend.userpass.path}/users/${var.vault_operator_username}"
  ignore_absent_fields = true

  data_json = jsonencode({
    password       = random_password.operator.result
    token_policies = []
  })
}

resource "vault_identity_entity" "operator" {
  name = var.vault_operator_username
  metadata = {
    managed_by = "terraform"
    kind       = "human"
  }
}

### Binds the userpass login to the entity, so a login through this backend
### carries entity_id and therefore group membership.
resource "vault_identity_entity_alias" "operator" {
  name           = var.vault_operator_username
  mount_accessor = vault_auth_backend.userpass.accessor
  canonical_id   = vault_identity_entity.operator.id

  depends_on = [vault_generic_endpoint.operator]
}
