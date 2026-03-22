### Secret KV2 mount
resource "vault_mount" "kvv2" {
  path        = var.secret_mount
  type        = "kv"
  options     = { version = "2" }
  description = "KV Version 2 secret engine mount"
}

### Minio credentials
resource "random_password" "minio_secret_key" {
  length           = 32
  special          = false
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
