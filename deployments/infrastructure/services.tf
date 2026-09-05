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

### Tempo's WAL and local block staging. Completed blocks go to MinIO (the
### `tempo` bucket, deployments/applications/storage.tf), so this only ever
### holds what has not been flushed yet — same split as loki_data.
resource "nomad_dynamic_host_volume" "tempo_data" {
  name      = "tempo_data"
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

### embark's model artifacts and its own cache. Sized for ONNX weights: the
### embeddinggemma-q8 ModelKit alone is ~300 MiB unpacked, and a reranker sits
### beside it. Not a cache that can be thrown away cheaply -- losing it means
### re-pulling every model from the registry on the next start.
###
### Pinned to the same node as the embark job (deployments/applications's
### `embark_hostname`). The two are a pair: move one and the job stops
### placing, because a host volume does not follow it.
resource "nomad_dynamic_host_volume" "embark_data" {
  name      = "embark_data"
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

### registry-ui's cache. Small on purpose: it holds manifest digests and
### rendered model cards (tens of KB today), never a model layer. It exists
### so a restart costs no re-walk, since a cards row is keyed by a content
### digest and can never go stale.
resource "nomad_dynamic_host_volume" "registry_ui_data" {
  name      = "registry_ui_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "1 GiB"
  capacity_min = "100 MiB"

  constraint {
    attribute = "$${attr.unique.hostname}"
    value     = "radxa-dragon-q6a"
  }

  capability {
    access_mode     = "single-node-writer"
    attachment_mode = "file-system"
  }
}

### OpenViking's workspace and RAGFS's local scratch.
### The vectors live in Postgres and the blobs in MinIO, so this is working
### state rather than the store itself.
resource "nomad_dynamic_host_volume" "openviking_data" {
  name      = "openviking_data"
  namespace = "default"
  plugin_id = "mkdir"
  node_pool = "default"

  capacity_max = "10 GiB"
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

### State for the `acme` certificate-renewal job below.
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
    # The registry job (deployments/applications/services/registry.hcl) runs
    # on ubuntu, and its firewall rule lives with it in the applications
    # root. The rule that used to sit here opened 5000/5001 LAN-wide on this
    # host for a service that never ran.
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
    # Redis cache on radxa-dragon-q6a. Narrowed from LAN-wide now that a
    # caller exists: embark is registered in redis_cache_consumers
    # (database.tf) and runs on jetson-orin-nano. Add a node here
    # when its job joins that list, or it fails to reach the cache.
    redis = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.2.46 to any port 6379 proto tcp",
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
    # oauth2-proxy on radxa-dragon-q6a (L1). Only HAProxy (firebat) calls it
    # directly; no direct LAN access is needed since the gate's whole point
    # is that traffic goes through HAProxy first.
    # Three proxies, three ports: 4180 gates dash, 4181 registry-ui, 4182
    # OpenViking. All admit HAProxy's node alone, which is why the edge is the
    # only route in.
    oauth2_proxy = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.2.30 to any port 4180 proto tcp",
        "allow from 192.168.2.30 to any port 4181 proto tcp",
        "allow from 192.168.2.30 to any port 4182 proto tcp",
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
    {
      minio_secret = vault_kv_secret_v2.minio_credentials.path
      # Nomad's own OIDC discovery document, which F10 turned on by setting
      # `server { oidc_issuer = ... }` in
      # bootstrap/roles/nomad_server/templates/nomad.hcl.j2. That Ansible
      # variable is the source of truth for the host; change it there and
      # this must follow. Served through the HAProxy edge on the public
      # Let's Encrypt wildcard, so MinIO needs no extra trust bundle.
      nomad_oidc_config_url = "https://nomad.lab.orangecluster.nl/.well-known/openid-configuration"
    }
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
      grafana_oidc_secret        = vault_kv_secret_v2.grafana_oidc_client.path
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
      ### Only consumer is the "Open Grafana" link in the Telegram alert
      ### template. It does NOT feed the OIDC redirect URI — GF_SERVER_ROOT_URL
      ### does — but a node address here ships alerts pointing somewhere the
      ### edge no longer matches.
      grafana_external_url = "https://grafana.lab.orangecluster.nl"
    }
  )
  depends_on = [nomad_dynamic_host_volume.grafana_data]
}

### Alloy (system job, all nodes) — ships journald and Nomad task logs to Loki.
### Replaced Promtail, which reached end of life on 2 March 2026. Loki itself
### lives in the applications layer because it depends on the Loki MinIO bucket
### creds (provisioned there).
resource "nomad_job" "alloy" {
  jobspec = templatefile("${path.module}/services/alloy.hcl", {})
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
      # L3/L4: the dash job (deployments/applications), colocated with
      # oauth2-proxy on radxa-dragon-q6a, so these are loopback addresses
      # rather than computed cross-root references -- the applications
      # and infrastructure roots hold separate state with no link between
      # them (same cross-root shape as the memex client lookup in
      # deployments/applications/services.tf). Literals, like every
      # other node address in this repo (e.g. applications/services.tf's
      # phoenix_host = "192.168.2.29"). Two upstreams since L4 split dash
      # into a frontend task (port 8000) and a backend task (port 8001);
      # the backend one is path-scoped to `/api/status` in
      # oauth2-proxy.hcl's own OAUTH2_PROXY_UPSTREAMS value.
      dash_frontend_upstream = "http://127.0.0.1:8000"
      dash_backend_upstream  = "http://127.0.0.1:8001/api/status"
    }
  )
}

### A second oauth2-proxy, gating registry-ui on its own hostname. The job
### above says this pattern is meant to be copied; this is the first copy.
### Same OIDC client and cookie secret, different redirect URI, different
### listen port, different upstreams.
resource "nomad_job" "oauth2_proxy_registry_ui" {
  jobspec = templatefile(
    "${path.module}/services/oauth2-proxy-registry-ui.hcl",
    {
      oidc_secret   = vault_kv_secret_v2.oauth2_proxy_registry_ui_oidc_client.path
      cookie_secret = vault_kv_secret_v2.oauth2_proxy_registry_ui_cookie_secret.path
      redirect_url  = local.registry_ui_redirect_url

      # registry-ui's frontend task (8002) and backend task (8003), both
      # colocated with this proxy on radxa-dragon-q6a, so loopback. The
      # backend entry is path-scoped, and a path-scoped upstream matches
      # EXACTLY rather than as a prefix.
      frontend_upstream = "http://127.0.0.1:8002"
      backend_upstream  = "http://127.0.0.1:8003/api/registry"
    }
  )
}

### OV1: the third proxy, gating OpenViking. Unlike its two siblings it
### forwards the Vault ID token upstream, because OpenViking validates that
### same token itself.
resource "nomad_job" "oauth2_proxy_openviking" {
  jobspec = templatefile(
    "${path.module}/services/oauth2-proxy-openviking.hcl",
    {
      oidc_secret   = vault_kv_secret_v2.oauth2_proxy_openviking_oidc_client.path
      cookie_secret = vault_kv_secret_v2.oauth2_proxy_openviking_cookie_secret.path
      redirect_url  = local.openviking_redirect_url

      # OpenViking serves its API and Studio from one port, colocated with
      # this proxy on radxa-dragon-q6a, so a single loopback upstream.
      upstream = "http://127.0.0.1:1933"
    }
  )
}

### NATS+JetStream
resource "nomad_job" "nats" {
  jobspec    = templatefile("${path.module}/services/nats.hcl", {})
  depends_on = [nomad_dynamic_host_volume.nats_data]
}

### Redis — shared cache. Callers never receive a static password: a
### consumer job in `local.redis_cache_consumers` (database.tf)
### opts in with `vault { role = "redis-cache-<job>" }` and reads its own
### `redis/creds/cache-<job>` for a credential minted fresh per render and
### revoked on lease expiry.
###
### `detach = false`: the default (`true`) returns as soon as the job is
### REGISTERED, not once its alloc is actually up. database.tf's
### Vault connection dials this job's address at apply time and needs it
### reachable by then, not just accepted by the scheduler.
resource "nomad_job" "redis" {
  jobspec = templatefile(
    "${path.module}/services/redis.hcl",
    { redis_admin_secret = vault_kv_secret_v2.redis_admin_credentials.path }
  )
  detach = false
}

### --- acme -----------------------------------------------------------------

### ACME certificate renewal for the *.lab.orangecluster.nl edge.
###
### A periodic job runs lego's DNS-01 challenge against TransIP and writes the
### issued material to Vault KV2, where the edge proxy reads it. HAProxy
### templates that secret into the PEM it serves, so a failed renewal
### eventually takes every routed service down together.
### The TransIP API credential. Written by hand rather than by Terraform: it
### is issued from the TransIP control panel and shown once, so there is no
### resource that could generate it. Terraform never reads its value, only
### its path — the acme job's own `vault {}` block reads the value at
### deploy time with its own Vault token — so the path is a plain string,
### not a `data "vault_kv_secret_v2"` source (deprecated in favor of the
### ephemeral resource, which cannot flow into templatefile's non-write-only
### vars map anyway; a literal string sidesteps that rather than fighting
### it, matching hermes's external secrets in applications/services.tf).
###
### The key pair is created with 'whitelisted IP' unchecked, so lego's client
### (which requests a global token by default) works from any address. A
### whitelisted key would mint tokens that authenticate but fail on every
### subsequent call.
resource "nomad_job" "acme" {
  jobspec = templatefile(
    "${path.module}/services/acme.hcl",
    {
      vault_role     = vault_jwt_auth_backend_role.acme.role_name
      transip_secret = "${var.secret_mount}/data/default/acme/transip"
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

### --- backups --------------------------------------------------------------

### Nomad backup jobs
resource "nomad_job" "backup_postgres" {
  jobspec = templatefile(
    "${path.module}/services/backup-postgres.hcl",
    {
      postgres_secret = vault_kv_secret_v2.backup_postgres_db_credentials.path
      gcs_secret      = vault_kv_secret_v2.backup_postgres_gcs_credentials.path
      postgres_host   = "192.168.2.30"
      gcs_bucket      = var.gcs_backup_bucket
    }
  )
}

resource "nomad_job" "backup_minio" {
  jobspec = templatefile(
    "${path.module}/services/backup-minio.hcl",
    {
      minio_secret = vault_kv_secret_v2.backup_minio_s3_credentials.path
      gcs_secret   = vault_kv_secret_v2.backup_minio_gcs_credentials.path
      minio_host   = "192.168.2.29"
      gcs_bucket   = var.gcs_backup_bucket
    }
  )
}
