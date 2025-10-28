### Dynamic Host Volume Example
resource nomad_dynamic_host_volume "example" {
  name      = "example"
  namespace = "default"
  plugin_id = "mkdir"

  capacity_max = "12 GiB"
  capacity_min = "1.0 GiB"

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }

  constraint {
    attribute = "$${attr.kernel.name}"
    value     = "linux"
  }
}

### Postgres
resource "nomad_job" "postgres" {
    jobspec = templatefile("${path.module}/services/postgres.hcl", { postgres_secret = vault_kv_secret_v2.postgres_root_credentials.path })
}
