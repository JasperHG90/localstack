data "consul_service" "minio" {
  name       = "minio"
  datacenter = "localstack"
}

data "consul_service" "postgres" {
  name       = "postgres-db"
  datacenter = "localstack"
}

ephemeral "vault_kv_secret_v2" "minio_admin" {
  mount = var.secret_mount
  name  = "default/minio/localstack"
}

ephemeral "vault_kv_secret_v2" "postgres_admin" {
  mount = var.secret_mount
  name  = "default/postgres/localstack"
}

### Firewall rules for application services
locals {
  firewall_rules = {
    # Phoenix on orange_pi_4a
    phoenix = {
      host     = "192.168.2.29"
      ssh_user = "orangepi"
      rules = [
        "allow from 192.168.0.0/16 to any port 6006 proto tcp",
        "allow from 192.168.0.0/16 to any port 4317 proto tcp",
      ]
    }
    # Memex on jetson_nano
    memex = {
      host     = "192.168.2.46"
      ssh_user = "localstack"
      rules = [
        "allow from 192.168.0.0/16 to any port 8000 proto tcp",
      ]
    }
    # Hermes on radxa (only HAProxy + Memex can reach it)
    hermes = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.2.30 to any port 8642 proto tcp",
        "allow from 192.168.2.30 to any port 9119 proto tcp",
        "allow from 192.168.2.46 to any port 8642 proto tcp",
      ]
    }
    # Loki on ubuntu (rpi4b) — LAN only (Promtail clients across the cluster)
    loki = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.0.0/16 to any port 3100 proto tcp",
      ]
    }
    # MLflow on radxa-dragon-q6a (firebat CPU is fully reserved; port 5050 since 5000/5001 are reserved for the Docker registry on firebat)
    mlflow = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.0.0/16 to any port 5050 proto tcp",
      ]
    }
  }
}

resource "null_resource" "firewall" {
  for_each = local.firewall_rules

  triggers = {
    rules = jsonencode(each.value.rules)
    host  = each.value.host
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

### Arize Phoenix
resource "nomad_job" "phoenix" {
  jobspec = templatefile(
    "${path.module}/services/phoenix.hcl",
    {
      phoenix_secret = vault_kv_secret_v2.phoenix_db_credentials.path
      postgres_host  = data.consul_service.postgres.service[0].node_address
      phoenix_host   = "192.168.2.29"
    }
  )
  depends_on = [postgresql_database.database]
}

### Hermes
resource "nomad_job" "hermes" {
  jobspec = templatefile(
    "${path.module}/services/hermes.hcl",
    {
      hermes_hostname = "radxa-dragon-q6a"
      hermes_host     = "192.168.2.50"
      hermes_version  = "0.10.0-memex-v1.0.0rc6-r1"
      # Branch, tag, or full commit SHA — pin to a SHA for reproducibility.
      external_skills_jasperhg90_ref = "main"
      memex_host                     = "192.168.2.46"
      memex_auth_secret              = "${var.secret_mount}/data/default/hermes/memex_auth"
      github_secret                  = "${var.secret_mount}/data/default/hermes/github"
      telegram_secret                = "${var.secret_mount}/data/default/hermes/telegram"
      openrouter_secret              = "${var.secret_mount}/data/default/hermes/openrouter"
      ollama_secret                  = "${var.secret_mount}/data/default/hermes/ollama"
      email_secret                   = "${var.secret_mount}/data/default/hermes/email"
      nomad_secret                   = "${var.secret_mount}/data/default/hermes/nomad"
      api_server_secret              = vault_kv_secret_v2.hermes_api_server.path
      telegram_allowed_users         = var.telegram_allowed_users
      hermes_email_address           = var.hermes_email_address
      hermes_digest_email            = var.hermes_digest_email
      soul_md                        = file("${path.module}/services/hermes/SOUL.md")
      skills = {
        for f in fileset("${path.module}/services/hermes/skills", "**/SKILL.md") :
        trimsuffix(f, "/SKILL.md") => file("${path.module}/services/hermes/skills/${f}")
      }
    }
  )
}

### Loki — central log aggregator on ubuntu (rpi4b), MinIO-backed
resource "nomad_job" "loki" {
  jobspec = templatefile(
    "${path.module}/services/loki.hcl",
    { loki_minio_secret = vault_kv_secret_v2.loki_minio_credentials.path }
  )
}

### Memex
resource "nomad_job" "memex" {
  jobspec = templatefile(
    "${path.module}/services/memex.hcl",
    {
      memex_postgres_secret = vault_kv_secret_v2.memex_db_credentials.path
      memex_minio_secret    = vault_kv_secret_v2.memex_minio_credentials.path
      memex_auth_secret     = vault_kv_secret_v2.memex_auth_keys.path
      memex_gemini_secret   = "${var.secret_mount}/data/default/memex/gemini"
      postgres_host         = data.consul_service.postgres.service[0].node_address
      minio_host            = data.consul_service.minio.service[0].node_address
      phoenix_host          = "192.168.2.29"
      memex_host            = "192.168.2.46"
      memex_version         = "1.0.0rc6"
    }
  )
  depends_on = [postgresql_database.database]
}

### MLflow — experiment + model tracking, Postgres backend + MinIO artifacts
resource "nomad_job" "mlflow" {
  jobspec = templatefile(
    "${path.module}/services/mlflow.hcl",
    {
      mlflow_postgres_secret = vault_kv_secret_v2.mlflow_db_credentials.path
      mlflow_minio_secret    = vault_kv_secret_v2.mlflow_minio_credentials.path
      postgres_host          = data.consul_service.postgres.service[0].node_address
      minio_host             = data.consul_service.minio.service[0].node_address
      mlflow_host            = "192.168.2.50"
      mlflow_version         = "2.20.0"
    }
  )
  depends_on = [postgresql_database.database, module.buckets]
}
