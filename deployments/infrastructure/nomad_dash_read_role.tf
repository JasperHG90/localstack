### Minimal read-only Nomad ACL policy for the dash status backend.
###
### No existing role fits: `nomad-workloads` (every job's default grant) is
### KV-only and carries no Nomad API capability at all
### (bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2).
### `nomad/creds/deploy` grants submit-job and host-volume-* -- write
### capability this read-only status endpoint must never hold.
### `nomad/creds/manage` is a full management token, brokered only through
### an interactive human Vault login (cli/src/localstack_cli/auth/broker.py),
### never usable by a Nomad job's own Workload Identity.
###
### `read-job` and `list-jobs` are exactly what `judge_all()`/`join()`
### need: `job_statuses()` calls `list-jobs`, `job_service_names()` calls
### `read-job` (cli/src/localstack_cli/api/nomad.py). `node { policy =
### "read" }` is `list_nodes()`'s own grant. Nothing else is granted: no
### submit-job, no host-volume-*, no alloc-exec.
resource "nomad_acl_policy" "dash_read" {
  provider    = nomad.manage
  name        = "dash-read"
  description = "Read-only Nomad access for the dash status backend"

  rules_hcl = <<-EOT
    namespace "default" {
      capabilities = [
        "read-job",
        "list-jobs",
      ]
    }

    node {
      policy = "read"
    }
  EOT
}

### Vault brokers the dash backend's Nomad token: `vault read
### nomad/creds/dash_read` mints a short-lived client token carrying only
### the `dash-read` policy.
resource "vault_nomad_secret_role" "dash_read" {
  backend  = "nomad"
  role     = "dash_read"
  type     = "client"
  policies = [nomad_acl_policy.dash_read.name]
}

### The read grant on that Nomad secrets-engine role. A dynamic Nomad
### credential is read through the same generic `{{ with secret "<path>" }}`
### template syntax as any other Vault secrets engine (see redis.hcl's own
### `{{ with secret "${redis_admin_secret}" }}`), so the dash job's own
### `vault {}` block reads this path directly -- no KV2 copy needed, since
### nothing here is a KV2 value.
resource "vault_policy" "dash_nomad_creds_read" {
  name = "dash-nomad-creds-read"

  policy = <<-EOT
    path "nomad/creds/dash_read" {
      capabilities = ["read"]
    }
  EOT
}

### A dedicated role on the shared `jwt-nomad` mount, selected via
### `vault { role = "dash" }` on the dash job. Same shape as
### `vault_jwt_auth_backend_role.acme` (acme.tf) and `.redis_cache`
### (redis_secrets_engine.tf). token_policies carries BOTH policies
### deliberately: naming a dedicated role REPLACES `nomad-workloads`
### rather than adding to it, and the dash job needs both its own KV
### prefix (none today, but the default grant costs nothing to keep) and
### this new Nomad-credential read.
resource "vault_jwt_auth_backend_role" "dash" {
  backend   = "jwt-nomad"
  role_name = "dash"
  role_type = "jwt"

  bound_audiences = ["vault.io"]
  bound_claims = {
    nomad_namespace = "default"
    nomad_job_id    = "dash"
  }

  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_type             = "service"
  token_policies         = ["nomad-workloads", vault_policy.dash_nomad_creds_read.name]
  token_period           = 1800
  token_explicit_max_ttl = 0
}
