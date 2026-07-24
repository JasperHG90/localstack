### Vault PKI engine backing TLS termination at the HAProxy edge.
###
### A single self-signed ROOT CA (no intermediate) — there is no external
### issuer to chain from in the home lab, so a root keeps the trust path one
### hop deep. Clients show "untrusted" until this CA is distributed to them;
### that distribution is deliberately out of scope here.
resource "vault_mount" "pki" {
  path        = "pki"
  type        = "pki"
  description = "PKI engine issuing TLS leaves for the *.localstack edge"

  # The mount's max lease bounds the root CA's own TTL, so it must cover the
  # 10y root. Leaf lifetime is bounded by the role below, not by this.
  default_lease_ttl_seconds = 259200    # 72h
  max_lease_ttl_seconds     = 315360000 # 10y
}

resource "vault_pki_secret_backend_root_cert" "root" {
  backend     = vault_mount.pki.path
  type        = "internal"
  common_name = "localstack Root CA"
  ttl         = "87600h" # 10y
  key_type    = "rsa"
  key_bits    = 4096
}

### Issuing/CRL URLs point at Vault directly (192.168.2.30:8200) rather than
### at vault.localstack: that hostname resolves through the HAProxy edge,
### which this ticket makes HTTPS-only, and a client fetching the CA it does
### not yet trust over TLS terminated by a leaf from that same CA cannot
### bootstrap. The direct address keeps CA/CRL retrieval on plain HTTP.
resource "vault_pki_secret_backend_config_urls" "urls" {
  backend                 = vault_mount.pki.path
  issuing_certificates    = ["http://192.168.2.30:8200/v1/${vault_mount.pki.path}/ca"]
  crl_distribution_points = ["http://192.168.2.30:8200/v1/${vault_mount.pki.path}/crl"]
}

### One wildcard *.localstack leaf covers every hostname the edge routes today
### (haproxy.hcl frontend ACLs) plus any added later, with one cert and one
### template. Wildcard blast radius is moot here: HAProxy terminates TLS
### centrally, so every key lives in that one alloc regardless.
resource "vault_pki_secret_backend_role" "haproxy" {
  backend          = vault_mount.pki.path
  name             = "haproxy"
  allowed_domains  = ["localstack"]
  allow_subdomains = true

  # No bare `localstack`, no localhost, no IP SANs: the edge only ever serves
  # <svc>.localstack. allow_localhost defaults to true and would otherwise let
  # this role mint localhost certs, which nothing here needs.
  allow_bare_domains          = false
  allow_localhost             = false
  allow_ip_sans               = false
  allow_wildcard_certificates = true

  key_type = "rsa"
  key_bits = 2048

  ttl     = 259200 # 72h — leaf lifetime requested by the job's template
  max_ttl = 259200 # 72h — hard ceiling on any leaf from this role
}

### Authorization grant (Q1: dedicated scoped policy + role, in Terraform).
###
### The shared `nomad-workloads` policy (Ansible-owned) grants nothing on a
### pki/ path, and widening it would let EVERY workload mint certs for the
### edge. Instead the HAProxy job gets its own JWT role and its own policy
### carrying exactly one capability: issue against the role above.
resource "vault_policy" "haproxy_pki" {
  name = "haproxy-pki"

  policy = <<-EOT
    path "${vault_mount.pki.path}/issue/${vault_pki_secret_backend_role.haproxy.name}" {
      capabilities = ["create", "update"]
    }
  EOT
}

### The `jwt-nomad` auth mount itself is created and configured in Ansible
### bootstrap (bootstrap/roles/nomad_server/tasks/main.yml), which holds the
### Vault bootstrap token; it is referenced here by name, the same way the
### nomad/ and consul/ secrets-engine mounts are in F5/F6. This role is a
### SECOND role on that mount, selected per-job via `vault { role = ... }`,
### leaving the default `nomad-workloads` role untouched for every other job.
###
### bound_claims pins the role to the haproxy job in the default namespace, so
### no other workload can log in through it even if it names the role.
### bound_audiences/user_claim/claim_mappings mirror the shared role
### (bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json) so the
### JWT Nomad mints under its `default_identity { aud = ["vault.io"] }` config
### validates here too.
resource "vault_jwt_auth_backend_role" "haproxy" {
  backend   = "jwt-nomad"
  role_name = "haproxy"
  role_type = "jwt"

  bound_audiences = ["vault.io"]
  bound_claims = {
    nomad_namespace = "default"
    nomad_job_id    = "haproxy"
  }

  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_type             = "service"
  token_policies         = [vault_policy.haproxy_pki.name]
  token_period           = 1800 # 30m, matching the shared workload role
  token_explicit_max_ttl = 0
}
