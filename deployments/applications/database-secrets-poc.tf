### S2 SPIKE — THROWAWAY. Everything in this file exists to answer one
### question: can Vault's database secrets engine mint a short-lived Postgres
### user that does an application's real work? The answer, the evidence and
### what R3 must carry forward are in docs/postgres-vault-dynamic-creds-spike.md.
###
### LIVE STATE, and it deliberately differs from this file. Standing on the
### cluster: the `database` mount, the `postgres-poc` connection, the `s2-poc`
### role, the `vault-dbengine-admin` Postgres role, and that role's password at
### the KV2 path `<secret_mount>/default/postgres/vault-dbengine-admin`. S1
### (Boundary) brokers these same credentials and would otherwise rebuild them.
### The KV2 entry holds a CREATEROLE credential, so it belongs on any list of
### what this spike left behind.
###
### Already destroyed: `nomad_job.s2_poc_dynamic_creds`,
### `vault_jwt_auth_backend_role.s2_poc` and `vault_policy.s2_poc_db_read`.
### They stay declared here because they are the working reference R3 copies,
### which means a full `terraform apply` of this root WILL recreate them. That
### is harmless (the job is `batch` and runs once) but it is not what anyone
### asked for. To put the cluster back, from deployments/applications:
###
###   CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} \
###     terraform destroy -var-file=./vars/prod.tfvars \
###     -target=nomad_job.s2_poc_dynamic_creds \
###     -target=vault_jwt_auth_backend_role.s2_poc \
###     -target=vault_policy.s2_poc_db_read
###
### The CONSUL_HTTP_TOKEN prefix is not optional: state lives in the Consul
### backend and every recipe in this directory's justfile sets it. Without it
### terraform cannot even read state, and fails with
### `403 ... lacks permission 'key:read' on "terraform/applications"`.
###
### R3 deletes this file once it ships the real thing.
###
### This lives in the applications root, not infrastructure, for one reason:
### infrastructure has no `postgresql` provider, so `vault-dbengine-admin`
### cannot be created there. Splitting the role from the Vault connection that
### authenticates as it would force a cross-root apply order.

locals {
  ### One knob for the whole write-only chain below, and the three consumers
  ### must be written in the SAME apply. Measured on 2026-08-03, not assumed:
  ### creating `postgresql_role.s2_poc_admin` in one targeted apply and
  ### `vault_database_secret_backend_connection.postgres_poc` in the next
  ### produced two different passwords, and Vault refused the config with
  ### `failed SASL auth ... password authentication failed`. An ephemeral value
  ### is regenerated on every run and persisted nowhere, so it is only shared
  ### by consumers that write during the same walk.
  ###
  ### An UNCHANGED version on an EXISTING resource is a genuine no-op — that is
  ### what makes routine applies safe. The hazard is a resource that WRITES:
  ### one being created, or one whose version moved. Bump this and let all
  ### three write together; never target a subset.
  s2_poc_admin_password_version = "2"

  ### memex, not ducklake. The grant test needs a table an application already
  ### owns, and ducklake has none — `pg_tables` in it is empty, so the
  ### read-only half of the test would have no subject there.
  s2_poc_database   = "memex"
  s2_poc_owner_role = "memex"

  ### Named in a local rather than read off the role resource: the connection's
  ### `allowed_roles` and the role's `db_name` would otherwise form a cycle.
  s2_poc_role_name = "s2-poc"
  s2_poc_job_id    = "s2-poc-dynamic-creds"
}

### The identity the database engine mints users AS. Deliberately NOT the
### `localstack` root: Vault can rotate a connection's root credential, and
### the postgres_exporter, `backup-postgres`'s pg_dumpall and this root's own
### postgresql provider all authenticate as `localstack`. Rotating it would
### take all three down at once.
###
### The password never enters Terraform state. That is not a nicety — it is
### the entire argument for keeping this engine's mount and config in
### Terraform at all, against the F5/F6 invariant that hands both to Ansible
### when a Vault engine needs a privileged external credential
### (deployments/infrastructure/consul_deploy_role.tf:7-15). That invariant
### exists to keep the credential out of the Consul-backed state file, and the
### write-only chain does exactly that. `random_password` the RESOURCE would
### not: it stores `result` in state in cleartext, which is why
### database.tf:56-67 is the wrong pattern to copy here.
ephemeral "random_password" "s2_poc_admin" {
  length  = 32
  special = false
}

### `roles` is set here as well as in the grant below, and it has to be.
### Measured on 2026-08-03: with `roles` left unset, the provider reconciles
### this role's memberships to the empty set on every UPDATE, silently
### stripping the membership `postgresql_grant_role` granted. Minting then
### fails with `permission denied to grant role "memex" (SQLSTATE 42501)` at
### the next `vault read database/creds/s2-poc` — long after the apply that
### broke it reported success. Naming the membership in both places keeps the
### two resources agreeing instead of fighting.
resource "postgresql_role" "s2_poc_admin" {
  name        = "vault-dbengine-admin"
  login       = true
  create_role = true
  roles       = [postgresql_role.role[local.s2_poc_owner_role].name]

  password_wo         = ephemeral.random_password.s2_poc_admin.result
  password_wo_version = local.s2_poc_admin_password_version
}

### WITH ADMIN OPTION is load-bearing, and only this resource can set it.
### From PostgreSQL 16 on, a CREATEROLE role may only grant memberships it
### holds ADMIN on, and the creation_statements below grant `memex` to every
### user they mint. `roles` above re-grants the plain membership on update but
### drops the admin option with it, so this must apply after.
###
### `depends_on` alone does NOT cover the case that comment names. It orders
### the two when both are being applied; it does nothing when a later apply
### changes ONLY the role, which is exactly what bumping
### `s2_poc_admin_password_version` does. That apply would strip the admin
### option and leave this resource believing it is still in place, and the
### breakage would surface as a failed `vault read` some time later.
### `replace_triggered_by` closes it: any change to the role forces this grant
### to be recreated in the same apply.
resource "postgresql_grant_role" "s2_poc_admin_owner" {
  role              = postgresql_role.s2_poc_admin.name
  grant_role        = postgresql_role.role[local.s2_poc_owner_role].name
  with_admin_option = true

  lifecycle {
    replace_triggered_by = [postgresql_role.s2_poc_admin]
  }
}

### disable_read is not optional here. The provider otherwise reads the secret
### back after writing it and stores the plaintext in the computed `data`
### attribute — putting the password into the Consul-backed state by the back
### door, which is the one thing this whole chain exists to prevent.
resource "vault_kv_secret_v2" "s2_poc_admin" {
  mount        = var.secret_mount
  name         = "default/postgres/vault-dbengine-admin"
  disable_read = true

  data_json_wo = jsonencode({
    username = postgresql_role.s2_poc_admin.name
    password = ephemeral.random_password.s2_poc_admin.result
  })
  data_json_wo_version = local.s2_poc_admin_password_version
}

resource "vault_mount" "database" {
  path        = "database"
  type        = "database"
  description = "Dynamic database credentials. Stood up by the S2 spike."
}

### `connection_url` keeps its {{username}}/{{password}} templates. They are
### how Vault substitutes the credential configured below; dropping them for
### "no secret in the URL" yields a config that passes `terraform validate`
### and then cannot authenticate.
resource "vault_database_secret_backend_connection" "postgres_poc" {
  backend       = vault_mount.database.path
  name          = "postgres-poc"
  allowed_roles = [local.s2_poc_role_name]

  postgresql {
    connection_url = "postgresql://{{username}}:{{password}}@${data.consul_service.postgres.service[0].node_address}:5432/${local.s2_poc_database}?sslmode=disable"
    username       = postgresql_role.s2_poc_admin.name

    password_wo         = ephemeral.random_password.s2_poc_admin.result
    password_wo_version = local.s2_poc_admin_password_version
  }

  depends_on = [postgresql_grant_role.s2_poc_admin_owner]
}

### The TTLs are short on purpose and are NOT production values. `max_ttl` is
### the one that matters: Nomad's template runner renews a renewable lease
### continuously, so a dynamic credential lives until max_ttl, and with it
### unset that is Vault's 768h default — the rotation test would renew quietly
### for a month and observe nothing.
###
### The membership grant is the whole experiment. Reproducing memex's grants
### statement by statement would be a second way to get this wrong; inheriting
### them from the role that already owns the objects is the honest test of
### whether a dynamic user can do the app's work.
###
### The third statement is not decoration, and it is this spike's main
### finding. Without it, a table the dynamic user CREATEs is owned by the
### dynamic user, and Postgres then refuses to drop that role:
###
###   ERROR: role "v-root-s2-poc-..." cannot be dropped because some objects
###   depend on it
###   DETAIL: owner of table s2_orphan_probe
###
### Vault reports `All revocation operations queued successfully!` anyway, and
### the supposedly revoked credential goes on logging in and querying.
### Measured on 2026-08-03. `SET ROLE` makes every object the user creates land
### on `memex` instead, so revocation succeeds and ownership matches what the
### static role produced. `session_user` still records which minted user acted,
### so the audit trail survives.
resource "vault_database_secret_backend_role" "poc" {
  backend = vault_mount.database.path
  name    = local.s2_poc_role_name
  db_name = vault_database_secret_backend_connection.postgres_poc.name

  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT \"${local.s2_poc_owner_role}\" TO \"{{name}}\";",
    "ALTER ROLE \"{{name}}\" SET ROLE \"${local.s2_poc_owner_role}\";",
  ]

  default_ttl = 120
  max_ttl     = 300
}

### THROWAWAY, destroyed at the end of the spike. F3 shipped this pattern in
### deployments/infrastructure/acme.tf:41-90 with the argument for it: a second
### role on the Ansible-owned `jwt-nomad` mount, selected per-job, so no other
### workload's authorization moves. Editing the shared nomad-workloads policy
### instead would hand every job on the cluster `database/creds/*`.
resource "vault_policy" "s2_poc_db_read" {
  name = "s2-poc-db-read"

  policy = <<-EOT
    path "database/creds/${local.s2_poc_role_name}" {
      capabilities = ["read"]
    }
  EOT
}

### token_policies carries nomad-workloads as well, for the reason acme.tf
### gives: a Nomad task performs a single JWT login and holds a single token,
### so naming a dedicated role REPLACES the default rather than adding to it.
### claim_mappings must mirror the shared role, whose policy is templated on
### identity.entity.aliases.<accessor>.metadata.*.
resource "vault_jwt_auth_backend_role" "s2_poc" {
  backend   = "jwt-nomad"
  role_name = "s2-poc"
  role_type = "jwt"

  bound_audiences = ["vault.io"]
  bound_claims = {
    nomad_namespace = "default"
    nomad_job_id    = local.s2_poc_job_id
  }

  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_type             = "service"
  token_policies         = ["nomad-workloads", vault_policy.s2_poc_db_read.name]
  token_period           = 1800
  token_explicit_max_ttl = 0
}

### THROWAWAY. Two tasks: one proves the minted user can do memex's work, one
### holds a connection pool past max_ttl so the rotation failure has a subject.
resource "nomad_job" "s2_poc_dynamic_creds" {
  jobspec = templatefile(
    "${path.module}/services/poc-dynamic-creds.hcl",
    {
      vault_role    = vault_jwt_auth_backend_role.s2_poc.role_name
      creds_path    = "database/creds/${local.s2_poc_role_name}"
      postgres_host = data.consul_service.postgres.service[0].node_address
      database      = local.s2_poc_database

      ### Comfortably past the role's max_ttl above, so the lease is certainly
      ### dead when the pool checks out rather than merely probably.
      idle_seconds = vault_database_secret_backend_role.poc.max_ttl + 60
    }
  )

  depends_on = [vault_database_secret_backend_role.poc]
}
