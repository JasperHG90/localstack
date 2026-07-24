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
resource "nomad_acl_policy" "deploy" {
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
