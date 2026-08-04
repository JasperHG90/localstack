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

### Nomad's OIDC issuer (F10). One definition, two consumers: the memex
### server trusts it, and the hermes client points its OIDC config at it.
### The string must be byte-identical in both, or provider selection fails.
locals {
  nomad_oidc_issuer = "https://nomad.lab.orangecluster.nl"

  ### Vault's `lab` OIDC provider, for HUMAN logins. Byte-identical to what
  ### Vault advertises and to the issuer in the human's client config, or
  ### provider selection by `iss` fails.
  vault_oidc_issuer = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
}

### The cross-root channel. The memex OIDC client is created in the
### infrastructure root; this reads its client_id back by static name, with no
### remote-state link. A public client returns an empty client_secret rather
### than erroring.
data "vault_identity_oidc_client_creds" "memex" {
  name = "memex"
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
        "allow from 192.168.2.46 to any port 8642 proto tcp",
      ]
    }
    # Loki on ubuntu (rpi4b) — cluster nodes only. Promtail is a system job, so
    # it ships from every node and each node address must stay on this list;
    # dropping one stops that node's logs silently. 192.168.2.30 doubles as the
    # HAProxy edge, which is how browsers reach Loki. The push and query APIs
    # have no authentication, so the LAN-wide rule is gone.
    loki = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.2.30 to any port 3100 proto tcp",
        "allow from 192.168.2.29 to any port 3100 proto tcp",
        "allow from 192.168.2.46 to any port 3100 proto tcp",
        "allow from 192.168.2.47 to any port 3100 proto tcp",
        "allow from 192.168.2.50 to any port 3100 proto tcp",
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
    # Bifrost LLM gateway on radxa-dragon-q6a — single OpenAI-compatible endpoint for all agent consumers (ADR-001)
    bifrost = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.0.0/16 to any port 8080 proto tcp",
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
      hermes_version  = "0.19.1-memex-v1.1.0"
      # Branch, tag, or full commit SHA — pin to a SHA for reproducibility.
      external_skills_jasperhg90_ref = "main"
      memex_host                     = "192.168.2.46"
      nomad_oidc_issuer              = local.nomad_oidc_issuer
      memex_auth_secret              = "${var.secret_mount}/data/default/hermes/memex_auth"
      github_secret                  = "${var.secret_mount}/data/default/hermes/github"
      telegram_secret                = "${var.secret_mount}/data/default/hermes/telegram"
      email_secret                   = "${var.secret_mount}/data/default/hermes/email"
      nomad_secret                   = "${var.secret_mount}/data/default/hermes/nomad"
      api_server_secret              = vault_kv_secret_v2.hermes_api_server.path
      bifrost_key_secret             = vault_kv_secret_v2.bifrost_hermes_key.path
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
  # Explicit dependency on the issued-key secret so terraform only deploys
  # Hermes after the Bifrost virtual key exists in Vault (operator-required).
  depends_on = [vault_kv_secret_v2.bifrost_hermes_key]
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
      postgres_host         = data.consul_service.postgres.service[0].node_address
      minio_host            = data.consul_service.minio.service[0].node_address
      phoenix_host          = "192.168.2.29"
      memex_host            = "192.168.2.46"
      nomad_oidc_issuer     = local.nomad_oidc_issuer
      vault_oidc_issuer     = local.vault_oidc_issuer
      memex_oidc_client_id  = data.vault_identity_oidc_client_creds.memex.client_id
      bifrost_host          = "192.168.2.50"
      memex_version         = "1.2.0"
      # Bifrost virtual key issued to Memex (default/memex/bifrost). Memex's
      # default/extraction/reflection models all call Bifrost /v1 with this key.
      bifrost_key_secret = vault_kv_secret_v2.bifrost_memex_key.path
    }
  )
  # Deploy Memex only after its Bifrost key exists in Vault.
  depends_on = [postgresql_database.database, vault_kv_secret_v2.bifrost_memex_key]
}

### Bifrost — LLM gateway: load-balances two Ollama Cloud keys, falls back to Gemini (ADR-001)
resource "nomad_job" "bifrost" {
  jobspec = templatefile(
    "${path.module}/services/bifrost.hcl",
    {
      bifrost_hostname = "radxa-dragon-q6a"
      bifrost_host     = "192.168.2.50"
      bifrost_version  = "1.6.7"
      # Externally seeded in Vault (not Terraform-managed):
      #   vault kv put secret/default/bifrost/ollama-personal API_KEY=...
      #   vault kv put secret/default/bifrost/ollama-xebia    API_KEY=...
      #   vault kv put secret/default/bifrost/ollama-proton   API_KEY=...
      #   vault kv put secret/default/bifrost/ollama-rituals  API_KEY=...
      #   vault kv put secret/default/bifrost/gemini          GOOGLE_API_KEY=...
      #   vault kv put secret/default/bifrost/credentials username=... password=...
      ollama_personal_secret     = "${var.secret_mount}/data/default/bifrost/ollama-personal"
      ollama_xebia_secret        = "${var.secret_mount}/data/default/bifrost/ollama-xebia"
      ollama_proton_secret       = "${var.secret_mount}/data/default/bifrost/ollama-proton"
      ollama_rituals_secret      = "${var.secret_mount}/data/default/bifrost/ollama-rituals"
      gemini_secret              = "${var.secret_mount}/data/default/bifrost/gemini"
      bifrost_credentials_secret = "${var.secret_mount}/data/default/bifrost/credentials"
      # config_store is Postgres (see bifrost.hcl); the bifrost role/DB are
      # provisioned in database.tf and the creds stored at default/bifrost/db.
      bifrost_postgres_host = data.consul_service.postgres.service[0].node_address
      bifrost_db_secret     = vault_kv_secret_v2.bifrost_db_credentials.path
    }
  )
  # Bifrost migrates its config_store schema on startup, so the DB must exist first.
  depends_on = [postgresql_database.database]
}

# Admin creds the bifrost provider authenticates with and Bifrost itself reads
# via env.BIFROST_ADMIN_USERNAME/PASSWORD. Externally seeded (see comment above).
ephemeral "vault_kv_secret_v2" "bifrost_admin" {
  mount = var.secret_mount
  name  = "default/bifrost/credentials"
}

# The bifrost terraform provider has no retry/wait, so a virtual_key create can
# 401/refuse against a not-yet-ready Bifrost. This gate polls /health (always
# whitelisted, even with auth enabled) until the gateway is up before the key
# resource runs.
resource "null_resource" "bifrost_ready" {
  depends_on = [nomad_job.bifrost]

  # Carry the endpoint and a hash of the jobspec. The jobspec hash forces this
  # gate to replace (and re-poll /health) on every Bifrost redeploy, so virtual
  # keys (which depend on this resource) are only touched after the gateway is
  # back up. Carrying the endpoint in triggers also makes the bifrost provider
  # (providers.tf) depend on this resource: the provider cannot configure until
  # Bifrost is up, instead of racing a restart against a hardcoded IP.
  triggers = {
    endpoint = "http://192.168.2.50:8080"
    jobspec  = sha1(nomad_job.bifrost.jobspec)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      for i in $(seq 1 60); do
        if curl -fsS ${self.triggers.endpoint}/health >/dev/null 2>&1; then
          echo "bifrost ready"
          exit 0
        fi
        echo "waiting for bifrost /health..."
        sleep 2
      done
      echo "bifrost did not become ready" >&2
      exit 1
    EOT
  }
}

# Hermes virtual key: allow-all on ollama + gemini. allowed_models=["*"] is the
# wildcard (Bifrost IsUnrestricted); key_ids=["*"] allows all upstream keys.
# Note: the wildcard does NOT bypass Bifrost's model catalog — a requested model
# must still exist in the catalog for the provider (plugins/governance/resolver.go
# IsModelAllowedForProvider). ollama models not in the catalog 403 as
# "Model not allowed for this virtual key" regardless of this allowlist.
resource "bifrost_virtual_key" "hermes" {
  name = "hermes"

  provider_configs = [
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]

  depends_on = [null_resource.bifrost_ready]
}

# Memex virtual key: allow-all on ollama + gemini. Same wildcard semantics as
# the Hermes key: allowed_models=["*"], key_ids=["*"]. See the Hermes comment
# for the model-catalog caveat.
resource "bifrost_virtual_key" "memex" {
  name = "memex"

  provider_configs = [
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]

  depends_on = [null_resource.bifrost_ready]
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
