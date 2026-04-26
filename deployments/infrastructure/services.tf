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

resource "nomad_dynamic_host_volume" "hermes_data" {
  name      = "hermes_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "5 GiB"
  capacity_min = "1 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "radxa-dragon-q6a"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

resource "nomad_dynamic_host_volume" "prometheus_data" {
  name      = "prometheus_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "50 GiB"
  capacity_min = "5 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "ubuntu"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

resource "nomad_dynamic_host_volume" "grafana_data" {
  name      = "grafana_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "5 GiB"
  capacity_min = "1 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "ubuntu"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

resource "nomad_dynamic_host_volume" "loki_data" {
  name      = "loki_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "10 GiB"
  capacity_min = "2 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "ubuntu"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

### Firewall rules for services (applied via SSH)
locals {
  firewall_rules = {
    # Postgres on firebat
    postgres = {
      host     = "192.168.2.30"
      ssh_user = "firebat"
      rules = [
        "allow from 192.168.0.0/16 to any port 5432 proto tcp",
      ]
    }
    # MinIO on orange_pi_4a
    minio = {
      host     = "192.168.2.29"
      ssh_user = "orangepi"
      rules = [
        "allow from 192.168.0.0/16 to any port 9000 proto tcp",
        "allow from 192.168.0.0/16 to any port 9001 proto tcp",
      ]
    }
    # HAProxy on firebat (LAN + Tailscale)
    haproxy = {
      host     = "192.168.2.30"
      ssh_user = "firebat"
      rules = [
        "allow from 192.168.0.0/16 to any port 80 proto tcp",
        "allow from 100.64.0.0/10 to any port 80 proto tcp",
        "allow from 192.168.0.0/16 to any port 8404 proto tcp",
        "allow from 100.64.0.0/10 to any port 8404 proto tcp",
      ]
    }
    # Docker registry on firebat
    registry = {
      host     = "192.168.2.30"
      ssh_user = "firebat"
      rules = [
        "allow from 192.168.0.0/16 to any port 5000 proto tcp",
        "allow from 192.168.0.0/16 to any port 5001 proto tcp",
      ]
    }
    # Prometheus on ubuntu (rpi4b) — LAN + Tailscale
    prometheus = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.0.0/16 to any port 9090 proto tcp",
        "allow from 100.64.0.0/10 to any port 9090 proto tcp",
      ]
    }
    # Grafana on ubuntu (rpi4b) — LAN + Tailscale
    grafana = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.0.0/16 to any port 3000 proto tcp",
        "allow from 100.64.0.0/10 to any port 3000 proto tcp",
      ]
    }
    # node-exporter — one rule per node, scraped by Prometheus on 192.168.2.47
    node_exporter_firebat = {
      host     = "192.168.2.30"
      ssh_user = "firebat"
      rules    = ["allow from 192.168.2.47 to any port 9100 proto tcp"]
    }
    node_exporter_orangepi4a = {
      host     = "192.168.2.29"
      ssh_user = "orangepi"
      rules    = ["allow from 192.168.2.47 to any port 9100 proto tcp"]
    }
    node_exporter_jetson = {
      host     = "192.168.2.46"
      ssh_user = "localstack"
      rules    = ["allow from 192.168.2.47 to any port 9100 proto tcp"]
    }
    node_exporter_ubuntu = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules    = ["allow from 192.168.2.47 to any port 9100 proto tcp"]
    }
    node_exporter_radxa = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules    = ["allow from 192.168.2.47 to any port 9100 proto tcp"]
    }
    # postgres_exporter sidecar on firebat
    postgres_exporter = {
      host     = "192.168.2.30"
      ssh_user = "firebat"
      rules    = ["allow from 192.168.2.47 to any port 9187 proto tcp"]
    }
  }
}

resource "null_resource" "firewall" {
  for_each = local.firewall_rules

  triggers = {
    rules = jsonencode(each.value.rules)
  }

  provisioner "remote-exec" {
    connection {
      host        = each.value.host
      user        = each.value.ssh_user
      private_key = file("${path.root}/../../.ssh/id_rsa")
    }

    inline = [for rule in each.value.rules : "sudo ufw ${rule}"]
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
    {
      openfang_password = random_password.openfang_basic_auth.result
    }
  )
}

### Node exporter (system job, all nodes)
resource "nomad_job" "node_exporter" {
  jobspec = templatefile("${path.module}/services/node-exporter.hcl", {})
}

### Prometheus
resource "nomad_job" "prometheus" {
  jobspec = templatefile(
    "${path.module}/services/prometheus.hcl",
    { consul_address = "192.168.2.30:8500" }
  )
  depends_on = [nomad_dynamic_host_volume.prometheus_data]
}

### Grafana
resource "nomad_job" "grafana" {
  jobspec = templatefile(
    "${path.module}/services/grafana.hcl",
    {
      grafana_secret             = vault_kv_secret_v2.grafana_admin_credentials.path
      cluster_overview_dashboard = file("${path.module}/services/grafana/cluster-overview.json")
    }
  )
  depends_on = [nomad_dynamic_host_volume.grafana_data]
}

### Promtail (system job, all nodes) — Loki itself lives in the applications layer
### because it depends on the Loki MinIO bucket creds (provisioned there).
resource "nomad_job" "promtail" {
  jobspec = templatefile("${path.module}/services/promtail.hcl", {})
}
