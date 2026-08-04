### The cluster's role taxonomy: `admin`, and the scaffold app-user tiers hang
### off. `developer` is F11's and lives in developer_group.tf.
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
    "app-memex-readers" = [vault_identity_entity.operator.id]
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
