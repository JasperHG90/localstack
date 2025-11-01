resource "vault_kv_secret_v2" "postgres_ducklake_owner_credentials" {
  mount = var.secret_mount
  name  = "default/postgres/ducklake_owner"
  data_json = jsonencode({
    username = "ducklake"
    password = random_password.postgres_ducklake_owner.result
  })
}

resource "vault_kv_secret_v2" "postgres_ducklake_reader_credentials" {
  mount = var.secret_mount
  name  = "default/postgres/ducklake_reader"
  data_json = jsonencode({
    username = "ducklake_reader"
    password = random_password.postgres_ducklake_reader.result
  })
}

resource "vault_kv_secret_v2" "minio_ducklake_writer_credentials" {
  mount = var.secret_mount
  name  = "default/minio/ducklake_writer"
  data_json = jsonencode({
    access_key = minio_accesskey.ducklake_writer.access_key
    secret_key = minio_accesskey.ducklake_writer.secret_key
  })
}

resource "vault_kv_secret_v2" "minio_ducklake_reader_credentials" {
  mount = var.secret_mount
  name  = "default/minio/ducklake_reader"
  data_json = jsonencode({
    access_key = minio_accesskey.ducklake_reader.access_key
    secret_key = minio_accesskey.ducklake_reader.secret_key
  })
}
