### Human identity: the accounts, groups and policies a person gets.
###
### Four sections: the userpass auth backend and the operator entity, the
### `developer` group, `admin`, and the app-user tier scaffold. Machine
### credentials live in machine_roles.tf, single sign-on in oidc.tf.

### --- human auth -----------------------------------------------------------

### Human auth backend.
###
### Before this, `vault auth list` held only jwt-nomad/ (workload identity) and
### token/. There was no way for a human to obtain an entity-bearing token, so
### nothing entity-gated — including this ticket's own OIDC assignment — could
### be exercised at all. The harness VAULT_TOKEN is root and reports
### entity_id: "", which is why a root token cannot stand in for this.
###
### Kept apart from oidc.tf: a later ticket may move human auth to a federated
### backend (Google was considered and deferred) without touching the OIDC
### stack.

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

### `email` is not decoration: it is the only source for the `email` scope's
### claim (oidc.tf), and Grafana refuses a login whose resolved email is empty.
### An entity with no `email` key renders the claim as an empty string, and the
### failure surfaces at the OIDC callback, not here.
### `ov_account` is the person's OpenViking account id, and it is deliberately
### NOT the entity name: this entity is a cluster-admin identity and the account
### is a data identity, so collapsing the two would put OpenViking's account
### namespace inside Vault's admin namespace. The identity-token role (oidc.tf)
### publishes this metadata key as a claim and ov.conf.json maps the account
### from it. An entity without this key gets no OpenViking account at all, which
### is what makes `fallback: null` in that config fail closed.
resource "vault_identity_entity" "operator" {
  name = var.vault_operator_username
  metadata = {
    managed_by = "terraform"
    kind       = "human"
    email      = var.vault_operator_email
    ov_account = var.vault_operator_ov_identity.account
    ov_user    = var.vault_operator_ov_identity.user
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

### --- login MFA -------------------------------------------------------------

### TOTP as a second factor on human logins.
###
### The per-person secrets are NOT here and must never be: that secret IS the
### second factor, so holding it in state would file both factors in one place.
### `just mfa_enroll <username>` mints one and writes the QR Vault returns.
### docs/vault-2fa.md is the long form.
resource "vault_identity_mfa_totp" "lab" {
  issuer                  = "vault.lab.orangecluster.nl"
  period                  = 30
  algorithm               = "SHA256"
  digits                  = 6
  key_size                = 20
  max_validation_attempts = 5
}

### SCOPED TO THE USERPASS MOUNT, and deliberately not to the `jwt-lab` one.
###
### Every human login that carries a password lands here, including the one
### Vault runs behind its own OIDC provider page — so a person reaching ov-dash
### or any other SSO app meets the challenge once, at Vault, per Vault session.
###
### `jwt-lab` stays out of it because the token posted there was already earned
### at this mount. ov-dash trades an ID token for a Vault token with no
### password and no prompt, and it cannot answer a challenge: an enforcement
### that reached that mount would break the sign-in it exists to protect.
###
### THAT IS WHY THIS NAMES THE ACCESSOR AND NOT AN ENTITY. Vault matches an
### enforcement wherever the named entity authenticates, mount included, so
### `identity_entity_ids = [operator]` — which this was until ov-dash learned
### the trade — challenges the jwt-lab login too and strands the operator at
### the first hop. Targets are a union: adding an entity id back here enforces
### on the union, not the intersection.
###
### Enroll everyone in `vault_openviking_consumers` BEFORE applying this.
### Mount-wide means veerle now meets the challenge on the only service she
### reaches, and an unenrolled account cannot complete the login at all:
### `just mfa_enroll veerle`. docs/vault-2fa.md carries the order.
resource "vault_identity_mfa_login_enforcement" "userpass" {
  name                  = "userpass-totp"
  mfa_method_ids        = [vault_identity_mfa_totp.lab.method_id]
  auth_method_accessors = [vault_auth_backend.userpass.accessor]
}

### --- openviking consumers -------------------------------------------------

### People who use OpenViking and nothing else on this cluster.
###
### What defines them is what they are NOT in. No `developer`, no `admin`, no
### app-user tier. The single Vault path they hold is the identity-token role,
### granted through the group at the end of this section.
###
### That absence is only worth as much as what checks it. Nomad gates on the
### `developer` group, and dash, the registry UI and Grafana gate on the
### `operators` assignment in oidc.tf -- which exists BECAUSE those three used
### `allow_all` and would otherwise have admitted anyone able to log in.
###
### The operator is deliberately NOT one of these. That entity carries
### `ov_account` too, but it reaches the same path through `developer`'s
### `identity/*`, and adding it here would say the two identities are the same
### kind of thing.

resource "random_password" "openviking_consumer" {
  for_each = var.vault_openviking_consumers

  length  = 32
  special = false
}

resource "vault_generic_endpoint" "openviking_consumer" {
  for_each = var.vault_openviking_consumers

  path                 = "auth/${vault_auth_backend.userpass.path}/users/${each.key}"
  ignore_absent_fields = true

  data_json = jsonencode({
    password       = random_password.openviking_consumer[each.key].result
    token_policies = []
  })
}

### Account and user are separate, and for a consumer the account is SHARED.
### Everyone sits in `lab` and is told apart by the user inside it: OpenViking
### isolates user scopes absolutely, measured in OV1 as a 403 on a cross-user
### read, while `viking://resources` stays common to the account. Giving each
### person their own account would isolate them from the shared half too.
###
### Both keys must be set. An entity missing one does NOT get refused: Vault
### renders an absent metadata key as an empty string, and upstream applies
### `fallback` only to a null, so the caller lands in an account named `""`.
### What keeps that unreachable is the ACL on the identity-token role, not the
### mapping.
resource "vault_identity_entity" "openviking_consumer" {
  for_each = var.vault_openviking_consumers

  name = each.key
  metadata = merge(
    {
      managed_by = "terraform"
      kind       = "human"
      ov_account = each.value.account
      ov_user    = each.value.user
    },
    each.value.email == null ? {} : { email = each.value.email },
  )
}

resource "vault_identity_entity_alias" "openviking_consumer" {
  for_each = var.vault_openviking_consumers

  name           = each.key
  mount_accessor = vault_auth_backend.userpass.accessor
  canonical_id   = vault_identity_entity.openviking_consumer[each.key].id

  depends_on = [vault_generic_endpoint.openviking_consumer]
}

### One path, read-only. Minting an identity token is the whole grant: the
### token is what OpenViking verifies, and Vault issues it for the calling
### entity only, so this cannot be used to act as anyone else.
resource "vault_policy" "openviking_user" {
  name = "openviking-user"

  policy = <<-EOT
    path "identity/oidc/token/${vault_identity_oidc_role.openviking.name}" {
      capabilities = ["read"]
    }
  EOT
}

resource "vault_identity_group" "openviking_user" {
  name     = "openviking-user"
  type     = "internal"
  policies = [vault_policy.openviking_user.name]

  member_entity_ids = [
    for username in keys(var.vault_openviking_consumers) :
    vault_identity_entity.openviking_consumer[username].id
  ]
}

### --- jwt-lab: ID tokens from the lab provider ----------------------------

### A second human auth mount that holds no credential of its own. ov-dash
### posts a provider ID token here, gets a Vault token for the person, spends
### it once on `identity/oidc/token/openviking` and revokes it
### (services/ov-dash.hcl in the applications root).
###
### That hop is the whole reason this mount exists. OpenViking pins one issuer
### and one audience, and they are the identity-token role's, so a provider ID
### token is not a credential it would accept. Trading here leaves ov-dash
### holding the token shape the cluster already takes: ov.conf.json stays
### pinned and hermes is untouched. The second factor is asked at Vault's own
### login page, which is the point — ov-dash's password form cannot answer an
### MFA challenge.
###
### `jwks_url` over plaintext loopback, not the public name. Vault's listener
### is 0.0.0.0:8200 with tls_disable (bootstrap/roles/vault_server), so this
### fetch never leaves the host and needs no CA. `oidc_discovery_url` would
### have to be the public https URL byte for byte, because the jwt plugin
### refuses a discovery document whose issuer differs from the URL it came
### from, and that means trusting the edge certificate Vault's own PKI issued.
###
### `bound_issuer` is what the `iss` claim is checked against, and it carries
### the PUBLIC issuer because that is what the provider stamps. Off `jwks_url`
### alone the issuer would go unchecked.
resource "vault_jwt_auth_backend" "lab" {
  type        = "jwt"
  path        = "jwt-lab"
  description = "ID tokens from the lab OIDC provider, traded for a Vault token."

  jwks_url     = "http://127.0.0.1:8200/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}/.well-known/keys"
  bound_issuer = "https://${var.vault_issuer_host}/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}"
}

### `bound_audiences` is the ov-dash client id, so only a token minted for that
### client can be traded here. An ID token for Grafana or the Nomad UI is
### refused.
###
### `user_claim = ov_user` is what binds the login to a person: Vault looks for
### an alias of that name on this mount and adopts the entity it belongs to.
### The claim exists only because the `openviking` scope templates it, so that
### scope is load-bearing for the login and not just for OpenViking.
###
### No `token_policies`. The mint grant rides the person's group —
### `openviking-user`, or `developer`'s `identity/*` — which attaches to the
### entity and therefore to any token issued for it on any mount. A policy here
### would be a second, weaker copy of that grant.
###
### Five minutes because the token is spent at once: one mint, one revoke-self.
### Nothing renews it and nothing stores it.
resource "vault_jwt_auth_backend_role" "ov_dash" {
  backend   = vault_jwt_auth_backend.lab.path
  role_name = "ov-dash"
  role_type = "jwt"

  bound_audiences = [vault_identity_oidc_client.ov_dash.client_id]
  user_claim      = "ov_user"

  token_type    = "service"
  token_ttl     = 300
  token_max_ttl = 300
}

### One alias per person, and a missing one fails at the NEXT hop rather than
### at the login: with no alias of the claimed name Vault creates a fresh
### entity instead of refusing, and that entity is in no group, so its token
### carries `default` alone and the mint answers 403. Fail-closed either way,
### but the error is Vault's permission denied at hop 3, not anything ov-dash
### says about claims.
###
### Such a login also leaves the invented entity and its alias behind on this
### accessor, and the next apply then fails with "already exists" -- the same
### Terraform-versus-JWT-mount collision the jwt-nomad note in oidc.tf records.
### Apply the mount, the role and these aliases in one step.
###
### The name is the `ov_user` value, not the username, because that is the
### claim the role reads. For the operator the two differ: the entity is
### `operator` and the claim is `jasper`.
###
### `ov_user` is a DATA identity, and this repo treats it as non-unique on
### purpose: two Nomad workloads already share `jasper`
### (var.vault_openviking_workloads). Two PEOPLE sharing one would collide on
### (mount accessor, name) here, so the precondition below asserts what the
### login quietly depends on. `sub` needs no assertion, being the entity UUID,
### at the cost of an alias no reader can match to a person.
resource "vault_identity_entity_alias" "ov_dash_operator" {
  name           = var.vault_operator_ov_identity.user
  mount_accessor = vault_jwt_auth_backend.lab.accessor
  canonical_id   = vault_identity_entity.operator.id
}

resource "vault_identity_entity_alias" "ov_dash_consumer" {
  for_each = var.vault_openviking_consumers

  name           = each.value.user
  mount_accessor = vault_jwt_auth_backend.lab.accessor
  canonical_id   = vault_identity_entity.openviking_consumer[each.key].id

  lifecycle {
    precondition {
      condition = length(distinct(concat(
        [var.vault_operator_ov_identity.user],
        [for person in var.vault_openviking_consumers : person.user],
      ))) == length(var.vault_openviking_consumers) + 1
      error_message = "Two people share one ov_user. The jwt-lab aliases are keyed on that claim, so the pair would collide on (mount accessor, name) and ov-dash sign-in would resolve one person to the other's entity."
    }
  }
}

### --- developer ------------------------------------------------------------

### The `developer` group: one human identity that covers everything a person
### does on this cluster. Bound to the operator entity through a group, so
### adding a second human is one `member_entity_ids` entry and the group name
### rides the OIDC `groups` claim (oidc.tf) to Nomad, Grafana and MinIO.
###
### THIS IS NOT A CONTAINMENT BOUNDARY, and no comment here should say it is.
### The holder can write `identity/*` and `sys/policies/acl/*`, so they can
### grant themselves anything short of `root` in three commands. Vault refuses
### to attach the `root` policy and refuses nothing else. That is the
### operator's deliberate choice: Developer and Deployer are one role here.
###
### What it does buy over the root token: it is per-person and can be revoked
### by removing the member from this group. NOT audit attribution — no audit
### device is enabled on this cluster.
resource "vault_policy" "developer" {
  name = "developer"

  policy = <<-EOT
    # The provider mints a child token lazily on first use and caches it per
    # ProviderMeta. A FAILED mint never populates the cache, so a missing
    # grant here surfaces as one error per resource, after refresh begins.
    # The live `default` policy does not grant this, and it appears in no
    # vault_* resource block.
    path "auth/token/create" {
      capabilities = ["create", "update"]
    }

    # Mounts and auth methods the infrastructure root manages.
    path "sys/mounts" {
      capabilities = ["read", "list"]
    }

    path "sys/mounts/secret" {
      capabilities = ["create", "read", "update", "delete"]
    }

    # Same shape as sys/mounts/secret above: an exact path, added when
    # redis_secrets_engine.tf first needed a `database`-type mount. A new
    # mount always needs its own line here -- there is no wildcard grant
    # over sys/mounts/*, deliberately, matching every other exact-path
    # grant in this policy.
    path "sys/mounts/redis" {
      capabilities = ["create", "read", "update", "delete"]
    }

    # Runtime paths INSIDE that mount (connections, roles) are a separate
    # grant from mounting/tuning it, same split as nomad/role/* and
    # consul/roles/* below being separate from any sys/mounts/* grant for
    # those two (Ansible-owned) mounts.
    path "redis/config/*" {
      capabilities = ["create", "read", "update", "delete"]
    }

    path "redis/roles/*" {
      capabilities = ["create", "read", "update", "delete"]
    }

    path "sys/auth" {
      capabilities = ["read", "list"]
    }

    path "sys/auth/userpass" {
      capabilities = ["create", "read", "update", "delete", "sudo"]
    }

    path "sys/mounts/auth/*" {
      capabilities = ["read"]
    }

    # Mount paths are EXACT MATCH, so the grants above do not cover `/tune`.
    # Both vault_mount.kvv2 and vault_auth_backend.userpass carry a
    # description, and changing one is an in-place tune.
    #
    # There are TWO auth-tune endpoints and they are not interchangeable.
    # The PROVIDER writes sys/mounts/auth/<path>/tune; the `vault auth tune`
    # CLI writes sys/auth/<path>/tune. Denied on the first, the provider
    # exits 0, reports "changed", leaves Vault untouched and writes the value
    # into state -- a shadowed variable at resource_auth_backend.go:222-225
    # discards the error. See hashicorp/terraform-provider-vault#2983.
    path "sys/mounts/secret/tune" {
      capabilities = ["create", "read", "update"]
    }

    path "sys/mounts/auth/userpass/tune" {
      capabilities = ["create", "read", "update"]
    }

    # `sudo` is required on this form and the mount grant does not confer it,
    # because sys/auth/* is root-protected.
    path "sys/auth/userpass/tune" {
      capabilities = ["create", "read", "update", "sudo"]
    }

    # Policy and identity management: creating users, groups and their grants.
    path "sys/policies/acl" {
      capabilities = ["list"]
    }

    path "sys/policies/acl/*" {
      capabilities = ["create", "read", "update", "delete"]
    }

    path "identity/*" {
      capabilities = ["create", "read", "update", "delete", "list"]
    }

    path "auth/userpass/users/*" {
      capabilities = ["create", "read", "update", "delete", "list"]
    }

    path "auth/jwt-nomad/role/*" {
      capabilities = ["create", "read", "update", "delete"]
    }

    # Secrets-engine roles the infrastructure root manages.
    path "nomad/role/*" {
      capabilities = ["create", "read", "update", "delete"]
    }

    path "consul/roles/*" {
      capabilities = ["create", "read", "update", "delete"]
    }

    # The KV domain this repo owns. `bootstrap/` is a separate mount, not a
    # subtree, so this policy does not name it. That is not a boundary: the
    # holder can grant themselves the mount in three commands.
    path "secret/data/default/*" {
      capabilities = ["create", "read", "update", "delete", "patch"]
    }

    path "secret/metadata/default/*" {
      capabilities = ["create", "read", "update", "delete", "list"]
    }

    # The glob does not cover the bare prefix, and without this
    # `vault kv list -mount=secret default` fails at the top level.
    path "secret/metadata/default" {
      capabilities = ["list"]
    }

    # Brokered tokens: `localstack login` (D2) and F8's provider cutover.
    # EXACT paths, not nomad/creds/* -- a wildcard would let any role be
    # brokered. Two are intended: `deploy` and, since G2, `manage`.
    path "nomad/creds/deploy" {
      capabilities = ["read"]
    }

    # G2's management role, for the two Nomad ACL resources in nomad_oidc.tf.
    # Wider than `deploy` by design: a management token does anything in Nomad.
    #
    # Not a new ceiling, but not for the reason an earlier draft gave. Writing
    # your own `nomad/role/manage` buys nothing, because the creds grants above
    # are exact paths -- you could create the role and not read it. The route
    # that already worked is overwriting `nomad/role/deploy` to
    # `type = "management"` (permitted by `nomad/role/*`) and reading
    # `nomad/creds/deploy`, which was already granted.
    #
    # So the ceiling is unchanged. What this grant changes is DETECTABILITY:
    # the old route clobbers a Terraform-managed role and shows up as drift on
    # the next plan. This one leaves no mark. See G2's risk section.
    path "nomad/creds/manage" {
      capabilities = ["read"]
    }

    path "consul/creds/deploy" {
      capabilities = ["read"]
    }
  EOT
}

### Binding through a group, not the entity and not the auth mount: adding a
### person is one entry here, and the group NAME is what the OIDC `groups`
### scope emits (oidc.tf) for Nomad, Grafana and MinIO to map.
###
### Note for anyone checking a token: the policy arrives via the group, so it
### appears in `identity_policies` and NOT in `policies`, which holds only
### `default`. A check asserting `developer` in `policies` fails every correct
### login.
resource "vault_identity_group" "developer" {
  name     = "developer"
  type     = "internal"
  policies = [vault_policy.developer.name]

  member_entity_ids = [vault_identity_entity.operator.id]
}

### The cluster's role taxonomy: `admin`, and the scaffold app-user tiers hang
### off. `developer` is F11's and is in the section above.
###
### See docs/cluster-roles.md for what each role is for. Two things worth
### knowing before reading further:
###
###   - A group grants nothing on its own. It has to be named by an OIDC
###     assignment (or carry Vault policies) before membership means anything.
###   - Neither `developer` nor `admin` is a containment boundary. Both can
###     reach root in a few commands. They buy per-person credentials and
###     revocation, not isolation.

### --- admin ------------------------------------------------------------------

### Wildcard mode, for when `developer`'s enumerated policy 403s on legitimate
### work. Deliberately not least-privilege: it exists so nobody reaches for the
### root token, which cannot be revoked without an unseal.
###
### `path "*"` alone is NOT enough. Vault picks the most specific match, so any
### exact path the `default` policy names would beat the glob and cap the
### holder at default's capabilities there. Each of default's paths is
### restated below; Vault unions capabilities across policies for the same
### path, so the restatement wins.
###
### Read from the live policy on 2026-08-02 (`vault policy read default`), not
### assumed. Three of them are not literal strings and must be copied verbatim:
### the two `{{identity.*}}` templates, which Terraform passes through a
### heredoc untouched and which render to the same path default's do, and
### `identity/oidc/provider/+/authorize`, where `+` is Vault's single-segment
### wildcard. Retype any of the three as a plain path and it stops matching.
resource "vault_policy" "admin" {
  name = "admin"

  policy = <<-EOT
    path "*" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    # Every path the `default` policy names, restated so the glob above is not
    # shadowed. Order does not matter to Vault; this order matches
    # `vault policy read default` for diffing.
    path "auth/token/lookup-self" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "auth/token/renew-self" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "auth/token/revoke-self" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/capabilities-self" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    # Templated. Renders to the same path default's does.
    path "identity/entity/id/{{identity.entity.id}}" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "identity/entity/name/{{identity.entity.name}}" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/internal/ui/resultant-acl" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/renew" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/leases/renew" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/leases/lookup" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "cubbyhole/*" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/wrapping/wrap" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/wrapping/lookup" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/wrapping/unwrap" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/tools/hash" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/tools/hash/*" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    path "sys/control-group/request" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }

    # `+` is Vault's single-segment wildcard, not a literal.
    path "identity/oidc/provider/+/authorize" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
    }
  EOT
}

### Terraform owns the group; it does NOT own who is in it.
###
### external_member_entity_ids = true is the whole point. `admin` is joined and
### left between applies during an incident, so membership must be a
### `vault write` that no later apply reverts. The app-user tiers below do the
### opposite deliberately (see their comment).
###
### The consequence is that leaving yourself in `admin` after an incident is
### invisible to every `terraform plan`. Checking is a habit, not a gate.
resource "vault_identity_group" "admin" {
  name                       = "admin"
  type                       = "internal"
  policies                   = [vault_policy.admin.name]
  external_member_entity_ids = true

  metadata = {
    description = "Break-glass. Join for the incident, leave after. Membership is not managed by Terraform; see docs/cluster-roles.md."
  }
}

### --- the app-user scaffold ---------------------------------------------------

### Per-application user tiers. F2 built the extension point and shipped it
### empty; memex (R6) is its first consumer. A consumer ticket adds its own
### entry here and its own members below.
###
### Naming convention is `app-<service>-<level>`, documented in
### docs/cluster-roles.md and NOT enforced here. Whether a level is per-app or
### per-resource is the consumer's call, because only the consumer knows how
### its service expresses levels.
###
### `policies = []` on every one, deliberately. These groups carry no Vault
### capability; they exist to be named by an OIDC assignment so a service can
### tell its own tiers apart. A group that grants Vault access is a different
### thing and belongs above.
locals {
  app_user_groups = {
    # >>> CONSUMER TICKETS: ADD YOUR TIER HERE. <<<
    #
    #   "app-minio-readers" = "Read-only access to MinIO buckets"
    #
    # Then bind it in your own vault_identity_oidc_assignment. Adding a person
    # is a Terraform edit to app_user_group_members below, which is the point:
    # a tier list should be reviewable. `admin` is the deliberate exception.
    "app-memex-admins"  = "Full access to memex through Vault SSO"
    "app-memex-readers" = "Read-only access to memex through Vault SSO"
  }
}

### Who is in each tier. Keyed by the same group name as the map above.
###
### This map is the other half of the extension point. Without it the tiers
### exist but admit nobody: `vault_identity_group.app_user` sets no members, so
### every tier ships empty and no OIDC assignment naming one can ever match.
###
### A tier with no key here lands empty, which is a valid resting state.
locals {
  app_user_group_members = {
    "app-memex-admins" = [vault_identity_entity.operator.id]
  }
}

resource "vault_identity_group" "app_user" {
  for_each = local.app_user_groups

  name     = each.key
  type     = "internal"
  policies = []

  # No external_member_entity_ids here. member_entity_ids is authoritative, so
  # a member added by hand shows as a diff on the next plan and is reverted.
  member_entity_ids = lookup(local.app_user_group_members, each.key, [])

  metadata = {
    description = each.value
  }
}

### The extension point, keyed by group name.
###
### >>> CONSUMER TICKETS: READ THIS, DO NOT EDIT IT. <<<
### Derived from the map above. Add your tier there, then bind YOUR OWN key:
###
###   group_ids = [local.app_user_group_ids["app-minio-readers"]]
###
### KEYED, NOT A FLAT LIST, and that is not cosmetic. An earlier revision
### exposed every tier's id in one list and told consumers to bind it. With one
### tier that is correct and with two it is a silent authorization bug: the
### first consumer's assignment starts admitting the second consumer's members,
### with nothing changing in the first consumer's own file to show it. Bind the
### key you own.
locals {
  app_user_group_ids = { for k, g in vault_identity_group.app_user : k => g.id }
}

### Every tier id, for the smoke client only. It is F2's throwaway proof that
### the extension point is wired, so admitting all tiers is what it is for.
### A real consumer must NOT use this.
locals {
  all_app_user_group_ids = values(local.app_user_group_ids)
}
