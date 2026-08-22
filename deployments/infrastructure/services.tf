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

resource "nomad_dynamic_host_volume" "nats_data" {
  name      = "nats_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "20 GiB"
  capacity_min = "2 GiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "radxa-dragon-q6a"
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
        "allow from 192.168.0.0/16 to any port 443 proto tcp",
        "allow from 100.64.0.0/10 to any port 443 proto tcp",
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
    # Prometheus on ubuntu (rpi4b) — cluster-internal only. Grafana's datasource
    # dials the node address from this same host; browsers arrive via HAProxy,
    # which already admits the LAN and the tailnet on 80/443. The query API has
    # no authentication, so it is not exposed to the LAN directly.
    prometheus = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.2.47 to any port 9090 proto tcp",
        "allow from 192.168.2.30 to any port 9090 proto tcp",
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
    # NOMAD PACK applications
    nomad_pack_applications_ubuntu = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.0.0/16 to any port 8080 proto tcp",
        "allow from 100.64.0.0/10 to any port 8080 proto tcp",
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
    # Redis cache on radxa-dragon-q6a. LAN-wide for now: no caller is wired
    # up yet (redis_secrets_engine.tf), so tighten this once one exists.
    redis = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.0.0/16 to any port 6379 proto tcp",
      ]
    }
    # NATS+JetStream on radxa-dragon-q6a (LAN-only; no auth in v1)
    nats = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.0.0/16 to any port 4222 proto tcp",
        "allow from 192.168.0.0/16 to any port 8222 proto tcp",
        "allow from 192.168.2.47 to any port 7777 proto tcp",
      ]
    }
  }
}

resource "null_resource" "firewall" {
  for_each = local.firewall_rules

  # timestamp() changes every plan, so every apply re-runs the ufw commands.
  # ufw allow is idempotent on an existing rule, so this is safe. This
  # self-heals drift caused by other ufw writes rebuilding the chain from
  # ufw's DB and dropping rules this resource declared (the N1 hazard).
  triggers = {
    rules      = jsonencode(each.value.rules)
    always_run = timestamp()
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
### The certificate is written to KV2 by the acme job at runtime rather than
### created by Terraform, so there is no resource to reference and no ordering
### to express here. If the secret is absent the cert template simply blocks
### until the acme job stores it.
resource "nomad_job" "haproxy" {
  jobspec = templatefile(
    "${path.module}/services/haproxy.hcl",
    {
      openfang_password = random_password.openfang_basic_auth.result
      tls_secret        = "${var.secret_mount}/data/default/haproxy/tls"
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
    {
      consul_address       = "192.168.2.30:8500"
      bifrost_admin_secret = vault_kv_secret_v2.prometheus_bifrost_admin.path
    }
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
      logs_dashboard             = file("${path.module}/services/grafana/logs.json")
      services_dashboard         = file("${path.module}/services/grafana/services.json")
      node_dashboard             = file("${path.module}/services/grafana/node-detail.json")
      nomad_dashboard            = file("${path.module}/services/grafana/nomad.json")
      postgres_dashboard         = file("${path.module}/services/grafana/postgres.json")
      minio_dashboard            = file("${path.module}/services/grafana/minio.json")
      ingress_dashboard          = file("${path.module}/services/grafana/ingress.json")
      nats_dashboard             = file("${path.module}/services/grafana/nats.json")
      bifrost_dashboard          = file("${path.module}/services/grafana/bifrost.json")
      alert_rules                = file("${path.module}/services/grafana/alert-rules.yaml")
      telegram_secret            = "${var.secret_mount}/data/default/grafana/telegram"
      telegram_alert_chat_id     = var.telegram_alert_chat_id
      grafana_external_url       = "http://192.168.2.47:3000"
    }
  )
  depends_on = [nomad_dynamic_host_volume.grafana_data]
}

### Promtail (system job, all nodes) — Loki itself lives in the applications layer
### because it depends on the Loki MinIO bucket creds (provisioned there).
resource "nomad_job" "promtail" {
  jobspec = templatefile("${path.module}/services/promtail.hcl", {})
}

### oauth2-proxy — OIDC forward-gate for the landing page (dash). Reusable
### pattern: R1 and R4 copy this job.
resource "nomad_job" "oauth2_proxy" {
  jobspec = templatefile(
    "${path.module}/services/oauth2-proxy.hcl",
    {
      oidc_secret   = vault_kv_secret_v2.oauth2_proxy_oidc_client.path
      cookie_secret = vault_kv_secret_v2.oauth2_proxy_cookie_secret.path
      redirect_url  = local.oauth2_proxy_redirect_url
    }
  )
}

### NATS+JetStream
resource "nomad_job" "nats" {
  jobspec    = templatefile("${path.module}/services/nats.hcl", {})
  depends_on = [nomad_dynamic_host_volume.nats_data]
}

### Redis — shared cache. Callers never receive a static password: a
### consumer job in `local.redis_cache_consumers` (redis_secrets_engine.tf)
### opts in with `vault { role = "redis-cache-<job>" }` and reads its own
### `redis/creds/cache-<job>` for a credential minted fresh per render and
### revoked on lease expiry.
###
### `detach = false`: the default (`true`) returns as soon as the job is
### REGISTERED, not once its alloc is actually up. redis_secrets_engine.tf's
### Vault connection dials this job's address at apply time and needs it
### reachable by then, not just accepted by the scheduler.
resource "nomad_job" "redis" {
  jobspec = templatefile(
    "${path.module}/services/redis.hcl",
    { redis_admin_secret = vault_kv_secret_v2.redis_admin_credentials.path }
  )
  detach = false
}
