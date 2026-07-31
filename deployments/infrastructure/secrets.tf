### Secret KV2 mount
resource "vault_mount" "kvv2" {
  path        = var.secret_mount
  type        = "kv"
  options     = { version = "2" }
  description = "KV Version 2 secret engine mount"
}

### Minio credentials
resource "random_password" "minio_secret_key" {
  length  = 32
  special = false
}

resource "vault_kv_secret_v2" "minio_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/minio/localstack"
  data_json = jsonencode({
    access_key = "minio"
    secret_key = random_password.minio_secret_key.result
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

### OpenFang basic auth password
resource "random_password" "openfang_basic_auth" {
  length  = 24
  special = false
}

resource "vault_kv_secret_v2" "openfang_basic_auth" {
  mount = vault_mount.kvv2.path
  name  = "default/openfang/basic_auth"
  data_json = jsonencode({
    username = "admin"
    password = random_password.openfang_basic_auth.result
  })
}

### Grafana admin password
resource "random_password" "grafana_admin" {
  length  = 24
  special = false
}

resource "vault_kv_secret_v2" "grafana_admin_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/grafana/admin"
  data_json = jsonencode({
    username = "admin"
    password = random_password.grafana_admin.result
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

### Postgres root password
resource "random_password" "postgres_root" {
  length  = 16
  special = false
}

resource "vault_kv_secret_v2" "postgres_root_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/postgres/localstack"
  data_json = jsonencode({
    username = "localstack"
    password = random_password.postgres_root.result
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

### Bifrost admin creds — synced copy for Prometheus /metrics basic_auth.
### The bifrost admin creds live at default/bifrost/credentials (externally
### seeded). Prometheus's nomad-workloads role grants read on default/prometheus/*
### only, so rather than widen that policy we copy the creds into Prometheus's
### own prefix here. Drift risk: rotating default/bifrost/credentials without a
### terraform apply leaves Prometheus scraping with stale creds (401).
### A data source (not an ephemeral read) is required: the synced creds persist
### in state via data_json, and ephemeral values cannot flow into a
### non-write-only attribute.
data "vault_kv_secret_v2" "bifrost_admin" {
  mount = var.secret_mount
  name  = "default/bifrost/credentials"
}

resource "vault_kv_secret_v2" "prometheus_bifrost_admin" {
  mount = vault_mount.kvv2.path
  name  = "default/prometheus/bifrost-admin"
  data_json = jsonencode({
    username = data.vault_kv_secret_v2.bifrost_admin.data.username
    password = data.vault_kv_secret_v2.bifrost_admin.data.password
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

### Human operator's userpass password. Generated, never in the repo or tfvars.
resource "vault_kv_secret_v2" "vault_operator_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/vault/operator"
  data_json = jsonencode({
    username = var.vault_operator_username
    password = random_password.operator.result
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

### Smoke-test OIDC client credentials. client_secret is provider-generated;
### it must reach KV2 and never a .tf literal. Note detect-private-key does
### NOT guard this: that hook matches PEM headers only.
resource "vault_kv_secret_v2" "oidc_smoke_client" {
  mount = vault_mount.kvv2.path
  name  = "default/vault/oidc-smoke"
  data_json = jsonencode({
    client_id     = vault_identity_oidc_client.smoke.client_id
    client_secret = vault_identity_oidc_client.smoke.client_secret
    issuer        = "https://${var.vault_issuer_host}/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}"
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}
