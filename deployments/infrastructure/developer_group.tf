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
