locals {
  node_host_volumes = {
    "localstack" = {
      "postgres" = {
        capacity_max = "100 GiB"
        capacity_min = "10 GiB"
      }
    }
    "orangepi4a" = {
      "minio_data" = {
        capacity_max = "3.5 TiB"
        capacity_min = "1.0 TiB"
      }
    }
  }

  dynamic_host_volumes = flatten([
    for host_name, volumes in local.node_host_volumes : [
      for volume_name, config in volumes : {
        host_name   = host_name
        volume_name = volume_name
        node_id     = var.node_ids[host_name]
        config      = config
      }
    ]
  ])
}

### Dynamic Host Volume Example
resource "nomad_dynamic_host_volume" "volumes" {
  for_each = { for vol in local.dynamic_host_volumes : "${vol.host_name}-${vol.volume_name}" => vol }

  name      = each.value.volume_name
  namespace = "default"
  plugin_id = "mkdir"
  node_id   = each.value.node_id

  capacity_max = each.value.config.capacity_max
  capacity_min = each.value.config.capacity_min

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
