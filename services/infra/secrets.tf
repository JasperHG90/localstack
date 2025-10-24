data "vault_kv_secret_v2" "postgres" {
  mount = var.secret_mount
  name  = "default/postgres/localstack"
}

resource "random_password" "postgres_root" {
  length           = 16
  special          = false
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "vault_kv_secret_v2" "postgres_root_credentials" {
  mount = var.secret_mount
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

resource "random_password" "postgres_ducklake" {
  length           = 16
  special          = false
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "vault_kv_secret_v2" "postgres_ducklake_credentials" {
  mount = var.secret_mount
  name  = "default/postgres/ducklake"
  data_json = jsonencode({
    username = "ducklake"
    password = random_password.postgres_ducklake.result
  })
}

resource "vault_kv_secret_v2" "minio_ducklake_credentials" {
  mount = var.secret_mount
  name  = "default/minio/ducklake"
  data_json = jsonencode({
    access_key = minio_accesskey.ducklake.access_key
    secret_key = minio_accesskey.ducklake.secret_key
  })
}
