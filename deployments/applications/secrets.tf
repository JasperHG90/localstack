resource "vault_kv_secret_v2" "postgres_credentials" {
  for_each = random_password.password
  mount = var.secret_mount
  name  = "default/postgres/${each.key}"
  data_json = jsonencode({
    username = each.key
    password = random_password.password[each.key].result
  })
}

resource "vault_kv_secret_v2" "minio_credentials" {
  for_each = minio_accesskey.users
  mount = var.secret_mount
  name  = "default/minio/${each.key}"
  data_json = jsonencode({
    access_key = each.value.access_key
    secret_key = each.value.secret_key
  })
}
