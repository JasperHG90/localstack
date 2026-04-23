resource "vault_kv_secret_v2" "postgres_credentials" {
  for_each = random_password.password
  mount    = var.secret_mount
  name     = "default/postgres/${each.key}"
  data_json = jsonencode({
    username = each.key
    password = random_password.password[each.key].result
  })
}

resource "vault_kv_secret_v2" "phoenix_db_credentials" {
  mount = var.secret_mount
  name  = "default/phoenix/postgres"
  data_json = jsonencode({
    username = postgresql_role.role["phoenix"].name
    password = random_password.password["phoenix"].result
  })
}

### Memex

resource "vault_kv_secret_v2" "memex_db_credentials" {
  mount = var.secret_mount
  name  = "default/memex/postgres"
  data_json = jsonencode({
    username = postgresql_role.role["memex"].name
    password = random_password.password["memex"].result
  })
}

resource "vault_kv_secret_v2" "memex_minio_credentials" {
  mount = var.secret_mount
  name  = "default/memex/minio"
  data_json = jsonencode({
    access_key = minio_accesskey.users["memex"].access_key
    secret_key = minio_accesskey.users["memex"].secret_key
  })
}

resource "random_id" "memex_admin_key" {
  byte_length = 32
}

resource "random_id" "memex_writer_key" {
  byte_length = 32
}

resource "vault_kv_secret_v2" "memex_auth_keys" {
  mount = var.secret_mount
  name  = "default/memex/auth"
  data_json = jsonencode({
    admin_key  = random_id.memex_admin_key.b64_url
    writer_key = random_id.memex_writer_key.b64_url
  })
}

resource "vault_kv_secret_v2" "minio_credentials" {
  for_each = minio_accesskey.users
  mount    = var.secret_mount
  name     = "default/minio/${each.key}"
  data_json = jsonencode({
    access_key = each.value.access_key
    secret_key = each.value.secret_key
  })
}
