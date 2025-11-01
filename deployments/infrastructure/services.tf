locals {
  node_ids_by_hostname = {
    "localstack" = "9ec2b8c5-69f4-3ad4-4868-b3d3ce414236"
    "orangepi4a" = "0aaa7eaf-4c06-bfb3-eaba-ead6de3096f5"
  }

  node_host_volumes = {
    "localstack" = {
      "postgres" = {
        capacity_max = "100 GiB"
        capacity_min = "10 GiB"
      },
      "docker_registry_data" = {
        capacity_max = "200 GiB"
        capacity_min = "20 GiB"
      },
      "docker_registry_auth" = {
        capacity_max = "10 MiB"
        capacity_min = "1 MiB"
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
        node_id     = local.node_ids_by_hostname[host_name]
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

### Docker registry
resource "nomad_job" "docker_registry" {
    jobspec = templatefile(
      "${path.module}/services/docker_registry.hcl", 
      { docker_registry_secret = vault_kv_secret_v2.docker_registry_credentials.path }
    )
}

### Minio
resource "nomad_job" "minio" {
    jobspec = templatefile(
      "${path.module}/services/minio.hcl", 
      { minio_secret = vault_kv_secret_v2.minio_credentials.path }
    )
}
