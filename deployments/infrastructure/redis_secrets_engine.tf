### Vault-brokered Redis credentials for cache callers.
###
### Every other datastore here (postgres, minio) hands a workload a STATIC
### password, read once from Vault KV and scoped by job id but never
### expiring. Redis is deliberately different: Vault's database secrets
### engine mints a fresh, short-lived ACL user per request and revokes it on
### lease expiry, so no caller — and no `terraform state` diff — ever
### carries a Redis password that outlives its job.
###
### This is the closest real analogue to memex's own workload-identity
### trust (R5, docs/workload-identity.md): memex verifies a caller's raw
### Nomad WI JWT itself, against Nomad's own JWKS. Redis cannot do that — it
### has no JWT support, unlike memex or MinIO's `identity_openid` — so the
### JWT is verified one hop earlier instead, by Vault's `jwt-nomad` mount,
### exactly as it already is for every job's KV reads. The caller still
### authenticates with nothing but its own Nomad workload identity; Vault is
### just the relying party instead of Redis.
###
### Mounted at `redis`, a dedicated path, NOT the generic `database` mount
### name HashiCorp's own docs default to. `database-secrets-poc.tf`
### (deleted in 19c1696, docs/postgres-vault-dynamic-creds-spike.md) already
### created and deliberately kept a `vault_mount` at `database/` from the
### *applications* root for an unfinished spike (S1,
### .loop/ledger.json:"blocked") — reusing that path here would either 400
### on "path already in use" or, worse, let a later `applications` apply
### silently destroy this engine, since that root's state may still track a
### `database` mount its config no longer declares. A dedicated path
### sidesteps that collision entirely rather than requiring state surgery
### before either root can apply.
resource "vault_mount" "redis" {
  path        = "redis"
  type        = "database"
  description = "Dynamic per-caller Redis ACL credentials"

  # The `developer` policy (developer_group.tf) only grants sys/mounts/*
  # on paths named there one at a time; explicit ordering, not an
  # attribute reference, is what makes the sys/mounts/redis grant land
  # before this mount is created in the same apply.
  depends_on = [vault_policy.developer]
}

### Vault authenticates to Redis as the `default` user — its password is
### services.tf's `requirepass`, set once in redis.hcl — and uses that
### connection's admin rights to create and drop every dynamic `cache-*`
### user below. No caller ever sees this password.
###
### `depends_on` covers BOTH things this connection needs to actually reach
### Redis, since `verify_connection` (default true) dials it during this
### apply: the job itself (services.tf's `nomad_job.redis` sets `detach =
### false` so it returns only once the alloc is up, not merely registered)
### and the firewall rule that opens 6379 (services.tf's
### `null_resource.firewall["redis"]`), which otherwise has no ordering
### relationship with this resource at all.
resource "vault_database_secret_backend_connection" "redis" {
  backend       = vault_mount.redis.path
  name          = "redis"
  plugin_name   = "redis-database-plugin"
  allowed_roles = ["cache-*"]

  redis {
    host     = "192.168.2.50"
    port     = 6379
    username = "default"
    password = random_password.redis_admin.result
    tls      = false
  }

  depends_on = [nomad_job.redis, null_resource.firewall]
}

### Redis cache consumers. Empty until a job actually needs the cache —
### add its Nomad job id here and `terraform apply` creates its own
### `database_secret_backend_role`, `vault_policy`, and `jwt_auth_backend_role`
### below, all three scoped to that job alone. A job then opts in with:
###
###   vault {
###     role = "redis-cache-<job-id>"
###   }
###
### and reads `redis/creds/cache-<job-id>` for a credential minted fresh per
### render.
###
### One role per consumer, not one shared role for all of them: the first
### version of this file used a single shared `cache` role gated only on
### `nomad_namespace = "default"` — which is nearly every job on this
### cluster (docs/workload-identity.md) — with every caller reading the
### identical `~cache:*` rule. That is rotation, not authorization: it does
### not deliver "callers authenticate with their own workload identity" so
### much as "every workload can read a Redis credential." This repo's own
### spike doc already weighed and rejected that shortcut in writing
### (docs/postgres-vault-dynamic-creds-spike.md: "widening the shared
### nomad-workloads policy... gives every workload on the cluster the
### ability to mint database users. Take the per-job cost."). Each entry
### here pays that per-job cost once, mirroring acme.tf's
### `vault_jwt_auth_backend_role.acme`, the working precedent this is
### modeled on.
locals {
  redis_cache_consumers = toset([
    # "memex",
    "embark",
  ])
}

### `~<job>:*`: each consumer's dynamic user is scoped to its OWN keyspace
### prefix, not the shared `cache:*` the first version of this file used —
### real per-caller isolation, not just per-caller credentials.
###
### `+@connection` is required, not optional: without it, every mainstream
### Redis client fails before it can do anything else, because `PING`,
### `SELECT`, and the `CLIENT SETINFO` handshake most clients send on
### connect all live in `@connection`, not `@read` or `@write`.
### `@scripting` (EVAL, used by most distributed-lock helpers) and pub/sub
### (`&*`) are deliberately left out — this engine is scoped to caching, not
### locking or messaging. Add them per-consumer if a future caller needs
### them.
###
### `default_ttl = 900` (15m), well under the usual 1h elsewhere in this
### repo: every dynamic user lives only in Redis's memory (no `aclfile`), so
### ANY restart of the redis task — OOM, reschedule, node reboot, not just
### a config change — wipes every outstanding user while Vault still
### considers their leases valid. A short TTL bounds that desync window to
### the time until the caller's next natural lease renewal instead of up to
### an hour of silent auth failures.
resource "vault_database_secret_backend_role" "cache" {
  for_each = local.redis_cache_consumers
  backend  = vault_mount.redis.path
  name     = "cache-${each.key}"
  db_name  = vault_database_secret_backend_connection.redis.name

  creation_statements = [
    jsonencode(["+@read", "+@write", "+@connection", "~${each.key}:*"])
  ]

  default_ttl = 900  # 15m; see the restart/lease-desync note above
  max_ttl     = 3600 # 1h
}

resource "vault_policy" "redis_cache_read" {
  for_each = local.redis_cache_consumers
  name     = "redis-cache-read-${each.key}"

  policy = <<-EOT
    path "redis/creds/cache-${each.key}" {
      capabilities = ["read"]
    }
  EOT
}

### The `jwt-nomad` auth mount, its config, and the default `nomad-workloads`
### role are Ansible-owned (bootstrap/roles/nomad_server/tasks/main.yml).
### This is a per-consumer role on that mount, selected via `vault { role =
### "redis-cache-<job>" }` — same pattern as `vault_jwt_auth_backend_role.acme`
### (acme.tf), bound to exactly one `nomad_job_id`, not a namespace-wide
### claim.
###
### token_policies carries BOTH policies deliberately, per the one-token
### rule (docs/workload-identity.md): naming a dedicated role REPLACES
### `nomad-workloads` rather than adding to it, so a caller that also needs
### its own KV secrets must keep that policy attached too.
resource "vault_jwt_auth_backend_role" "redis_cache" {
  for_each  = local.redis_cache_consumers
  backend   = "jwt-nomad"
  role_name = "redis-cache-${each.key}"
  role_type = "jwt"

  bound_audiences = ["vault.io"]
  bound_claims = {
    nomad_namespace = "default"
    nomad_job_id    = each.key
  }

  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_type             = "service"
  token_policies         = ["nomad-workloads", vault_policy.redis_cache_read[each.key].name]
  token_period           = 1800
  token_explicit_max_ttl = 0
}
