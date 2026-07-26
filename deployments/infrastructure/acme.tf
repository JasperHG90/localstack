### ACME certificate renewal for the *.lab.orangecluster.nl edge.
###
### A periodic job runs lego's DNS-01 challenge against TransIP and writes the
### issued material to Vault KV2, where the edge proxy reads it. HAProxy
### templates that secret into the PEM it serves, so a failed renewal
### eventually takes every routed service down together.

### lego needs durable state. It keeps the ACME account key under
### <path>/accounts and the issued bundle under <path>/certificates, and every
### periodic child job gets a fresh alloc dir. Without this volume lego
### re-registers and re-issues on every run, exhausting Let's Encrypt's
### 5-certs-per-identifier-set-per-week limit within days and locking out
### issuance until the window rolls.
resource "nomad_dynamic_host_volume" "acme_lego_state" {
  name      = "acme_lego_state"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "1 GiB"
  capacity_min = "100 MiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "ubuntu"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

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

### The TransIP API credential. Written by hand rather than by Terraform: it
### is issued from the TransIP control panel and shown once, so there is no
### resource that could generate it. Terraform only reads the path.
###
### The key pair is created with 'whitelisted IP' unchecked, so lego's client
### (which requests a global token by default) works from any address. A
### whitelisted key would mint tokens that authenticate but fail on every
### subsequent call.
data "vault_kv_secret_v2" "acme_transip" {
  mount = var.secret_mount
  name  = "default/acme/transip"
}

resource "nomad_job" "acme" {
  jobspec = templatefile(
    "${path.module}/services/acme.hcl",
    {
      vault_role     = vault_jwt_auth_backend_role.acme.role_name
      transip_secret = data.vault_kv_secret_v2.acme_transip.path
      secret_mount   = var.secret_mount
      tls_path       = "default/haproxy/tls"
      acme_domain    = var.acme_domain
      acme_email     = var.acme_email
      acme_server    = var.acme_server

      ### Separate state directory per ACME environment. lego namespaces
      ### accounts by server host but names certificate files after the domain
      ### alone, so one shared directory would let the staging bundle satisfy
      ### the production run's not-due check and republish an untrusted cert.
      acme_path = "/acme-state/${length(regexall("staging", var.acme_server)) > 0 ? "staging" : "production"}"
    }
  )

  depends_on = [nomad_dynamic_host_volume.acme_lego_state]
}
