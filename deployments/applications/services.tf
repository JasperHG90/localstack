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
      hermes_version  = "0.10.0-memex-v0.2.0"
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
      skill_cluster_watchdog         = file("${path.module}/services/hermes/skills/devops/cluster-watchdog/SKILL.md")
      skill_post_mortem              = file("${path.module}/services/hermes/skills/devops/post-mortem/SKILL.md")
      skill_sorting_hat              = file("${path.module}/services/hermes/skills/knowledge/sorting-hat/SKILL.md")
      skill_insight_linker           = file("${path.module}/services/hermes/skills/knowledge/insight-linker/SKILL.md")
      skill_daily_reflect            = file("${path.module}/services/hermes/skills/knowledge/daily-reflect/SKILL.md")
      skill_trader_advisor           = file("${path.module}/services/hermes/skills/finance/trader-advisor/SKILL.md")
      skill_market_analyst           = file("${path.module}/services/hermes/skills/finance/market-analyst/SKILL.md")
      skill_trend_scout              = file("${path.module}/services/hermes/skills/finance/trend-scout/SKILL.md")
      skill_blog_scraper             = file("${path.module}/services/hermes/skills/productivity/blog-scraper/SKILL.md")
      skill_medium_reader            = file("${path.module}/services/hermes/skills/productivity/medium-reader/SKILL.md")
      skill_researcher               = file("${path.module}/services/hermes/skills/productivity/researcher/SKILL.md")
      skill_collector                = file("${path.module}/services/hermes/skills/productivity/collector/SKILL.md")
      skill_hermes_watcher           = file("${path.module}/services/hermes/skills/devops/hermes-watcher/SKILL.md")
      skill_autoresearch_create      = file("${path.module}/services/hermes/skills/research/autoresearch-create/SKILL.md")
      skill_autoresearch_finalize    = file("${path.module}/services/hermes/skills/research/autoresearch-finalize/SKILL.md")
    }
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
      memex_version         = "0.2.0"
    }
  )
  depends_on = [postgresql_database.database]
}
