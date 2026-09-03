### Credentials Vault brokers to machines: to workloads through the shared
### `jwt-nomad` mount, and to the Terraform deployer through the Nomad and
### Consul secrets engines.
###
### Every workload role here has the same shape — a `vault_policy` naming one
### path, and a `vault_jwt_auth_backend_role` that attaches it alongside
### `nomad-workloads`. Read one and you have read them all; the comments say
### only what differs. Human identity is in identity.tf.

### --- the Nomad management credential --------------------------------------

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

### --- the deployer: Nomad --------------------------------------------------

### Nomad ACL policy for the Terraform deployer.
### Scoped to exactly what deploying this repo's nomad_job and
### nomad_dynamic_host_volume resources needs, and no more: no alloc-exec,
### no alloc-node-exec, no list-jobs / dispatch-job / read-logs / read-fs,
### and no node / agent / operator access.
###
### The host-volume-* capabilities are NAMESPACE capabilities that govern
### managing dynamic host volumes (create/read/delete the volume resource),
### which is what this root's nomad_dynamic_host_volume resources need. They
### are distinct from the `host_volume` mount policy (mount-readonly /
### mount-readwrite), which governs a job mounting a volume — the deployer
### creates volumes but does not mount them, so no mount policy is granted.
###
### `provider = nomad.manage`, not the default provider. Nomad requires a
### `management`-type token to write an ACL Policy at all — no capability
### inside a policy can grant that, so the operator's own session token
### (which `localstack env` deliberately demotes off root/management, per
### its own docstring) 403s here. `nomad.manage` (above) is a
### Vault-brokered, freshly-minted Nomad management token; every other
### ACL-management resource in this root already uses it.
resource "nomad_acl_policy" "deploy" {
  provider    = nomad.manage
  name        = "deploy"
  description = "Least-privilege policy for the Terraform deployer"

  rules_hcl = <<-EOT
    namespace "default" {
      capabilities = [
        "submit-job",
        "read-job",
        "host-volume-create",
        "host-volume-register",
        "host-volume-read",
        "host-volume-write",
        "host-volume-delete",
      ]
    }

    # Mounting a volume in a job is a separate grant from managing the volume
    # resource above. Every job this deployer submits that mounts a host
    # volume (memex, hermes, loki, prometheus, minio, grafana, nats, acme,
    # postgres) needs this, and the paired host-volume-* capabilities above
    # are already unscoped across the whole default namespace, so scoping
    # this one by name would only buy a false sense of isolation while
    # guaranteeing the next new or renamed volume 403s here again.
    host_volume "*" {
      capabilities = ["mount-readwrite"]
    }
  EOT
}

### Vault brokers the deployer's Nomad token: `vault read nomad/creds/deploy`
### mints a short-lived client token carrying only the `deploy` policy.
### The mount and its lease TTL are configured in Ansible bootstrap, which
### holds the Nomad management token this engine needs.
resource "vault_nomad_secret_role" "deploy" {
  backend  = "nomad"
  role     = "deploy"
  type     = "client"
  policies = [nomad_acl_policy.deploy.name]
}

### --- the deployer: Consul -------------------------------------------------

### Vault brokers the deployer's Consul token: `vault read consul/creds/deploy`
### mints a short-lived Consul ACL token carrying only the `deploy` policy,
### replacing the static god-mode Consul bootstrap token the deployer uses
### today. Consuming this brokered token in the provider is F8; F6 only stands
### up and proves the brokering path.
###
### The `consul` secrets engine mount, its `config/access` (which holds the
### Consul management token), AND the scoped `deploy` Consul ACL policy are all
### owned by Ansible bootstrap (bootstrap/playbooks/enable_consul_secrets.yml).
### Each requires the Consul management token, which the config-split invariant
### keeps out of Terraform. The pinned vault provider (~>5.3.0) attaches a
### Consul policy to a role only BY NAME via consul_policies; it cannot author
### the policy's rules through Vault. So the policy is created Consul-side in
### Ansible and referenced here by name, and Terraform authenticates to Vault
### only.
###
### ttl/max_ttl (30m/60m, in seconds) bound each minted token's lease; the
### deployer renews within a long run once F8 wires it up.
resource "vault_consul_secret_backend_role" "deploy" {
  backend         = "consul"
  name            = "deploy"
  consul_policies = ["deploy"]
  ttl             = 1800
  max_ttl         = 3600
}

### --- acme -----------------------------------------------------------------

### The write grant.
###
### The shared `nomad-workloads` policy grants a workload only READ on
### secret/data/<ns>/<job_id>/*, so the `acme` job can read its own TransIP
### credential with no help but cannot write the cert to haproxy's prefix.
### This policy adds exactly that one write. A KV2 data write needs no
### secret/metadata/* capability.
resource "vault_policy" "acme_tls_write" {
  name = "acme-tls-write"

  policy = <<-EOT
    path "${var.secret_mount}/data/default/haproxy/tls" {
      capabilities = ["create", "update"]
    }
  EOT
}

### The `jwt-nomad` auth mount, its config, and the default `nomad-workloads`
### role are Ansible-owned (bootstrap/roles/nomad_server/tasks/main.yml). This
### is a SECOND role on that mount, selected per-job via `vault { role }`,
### leaving every other workload on the default role untouched.
###
### token_policies carries BOTH policies deliberately. A Nomad task performs a
### single JWT login and holds a single token, so naming a dedicated role
### REPLACES nomad-workloads rather than adding to it. With only
### acme-tls-write attached, the job could write the cert but could not read
### the TransIP credential it needs to obtain one, and its template would
### block forever.
###
### claim_mappings must mirror the shared role: the nomad-workloads policy is
### templated on identity.entity.aliases.<accessor>.metadata.*, so without
### these mappings its paths resolve to nothing even when attached.
resource "vault_jwt_auth_backend_role" "acme" {
  backend   = "jwt-nomad"
  role_name = "acme"
  role_type = "jwt"

  bound_audiences = ["vault.io"]
  bound_claims = {
    nomad_namespace = "default"
    nomad_job_id    = "acme"
  }

  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_type             = "service"
  token_policies         = ["nomad-workloads", vault_policy.acme_tls_write.name]
  token_period           = 1800
  token_explicit_max_ttl = 0
}

### --- dash -----------------------------------------------------------------

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
### `vault_jwt_auth_backend_role.acme` and `.redis_cache`, both in this
### file. token_policies carries BOTH policies
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

### --- redis cache consumers ------------------------------------------------

### One `vault_policy` and one `jwt_auth_backend_role` per consumer, keyed off
### `local.redis_cache_consumers` in database.tf, where the engine and the
### matching `database_secret_backend_role` live.
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
### above, bound to exactly one `nomad_job_id`, not a namespace-wide
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
