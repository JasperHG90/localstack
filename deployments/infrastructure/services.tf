### Dynamic Host Volumes
resource "nomad_dynamic_host_volume" "postgres" {
  name      = "postgres"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "100 GiB"
  capacity_min = "10 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "firebat"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

resource "nomad_dynamic_host_volume" "minio_data" {
  name      = "minio_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "3.5 TiB"
  capacity_min = "1.0 TiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "orangepi4a"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

resource "nomad_dynamic_host_volume" "memex_data" {
  name      = "memex_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "50 GiB"
  capacity_min = "5 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "jetson-orin-nano"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

### Postgres
resource "nomad_job" "postgres" {
  jobspec = templatefile(
    "${path.module}/services/postgres.hcl",
    { postgres_secret = vault_kv_secret_v2.postgres_root_credentials.path }
  )
}

### Minio
resource "nomad_job" "minio" {
  jobspec = templatefile(
    "${path.module}/services/minio.hcl",
    { minio_secret = vault_kv_secret_v2.minio_credentials.path }
  )
}

### HAProxy
resource "nomad_job" "haproxy" {
  jobspec = templatefile(
    "${path.module}/services/haproxy.hcl",
    {}
  )
}
