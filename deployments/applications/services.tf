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
    # Phoenix on jetson_nano
    phoenix = {
      host     = "192.168.2.46"
      ssh_user = "localstack"
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
    # OpenFang on raspberry_pi_4b (HAProxy + Memex MCP only)
    openfang = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.2.30 to any port 50051 proto tcp",
        "allow from 192.168.2.46 to any port 50051 proto tcp",
      ]
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

### Arize Phoenix
resource "nomad_job" "phoenix" {
  jobspec = templatefile(
    "${path.module}/services/phoenix.hcl",
    {
      phoenix_secret = vault_kv_secret_v2.phoenix_db_credentials.path
      postgres_host  = data.consul_service.postgres.service[0].node_address
      phoenix_host   = "192.168.2.46"
    }
  )
  depends_on = [postgresql_database.database]
}

### OpenFang
resource "nomad_job" "openfang" {
  jobspec = templatefile(
    "${path.module}/services/openfang.hcl",
    {
      openfang_hostname  = "ubuntu"
      openfang_host      = "192.168.2.47"
      openfang_version   = "0.5.1"
      memex_host         = "192.168.2.46"
      memex_auth_secret  = vault_kv_secret_v2.openfang_memex_auth.path
      github_secret      = "${var.secret_mount}/data/default/openfang/github"
      telegram_secret        = "${var.secret_mount}/data/default/openfang/telegram"
      telegram_allowed_users = ["<REDACTED_TELEGRAM_USER_ID>"]
      minimax_secret         = "${var.secret_mount}/data/default/openfang/minimax"
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
      phoenix_host          = "192.168.2.46"
      memex_host            = "192.168.2.46"
      memex_version         = "0.0.38a"
    }
  )
  depends_on = [postgresql_database.database]
}
