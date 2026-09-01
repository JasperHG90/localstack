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

### Loki

resource "vault_kv_secret_v2" "loki_minio_credentials" {
  mount = var.secret_mount
  name  = "default/loki/minio"
  data_json = jsonencode({
    access_key = minio_accesskey.users["loki"].access_key
    secret_key = minio_accesskey.users["loki"].secret_key
  })
}

### Tempo

resource "vault_kv_secret_v2" "tempo_minio_credentials" {
  mount = var.secret_mount
  name  = "default/tempo/minio"
  data_json = jsonencode({
    access_key = minio_accesskey.users["tempo"].access_key
    secret_key = minio_accesskey.users["tempo"].secret_key
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

### Hermes

resource "random_id" "hermes_api_server_key" {
  byte_length = 32
}

resource "vault_kv_secret_v2" "hermes_api_server" {
  mount = var.secret_mount
  name  = "default/hermes/api_server"
  data_json = jsonencode({
    key = random_id.hermes_api_server_key.b64_url
  })
}

# Bifrost virtual key issued to Hermes. Stored under Hermes's own KV prefix
# (default/hermes/*) because the nomad-workloads role grants Hermes read only
# there. `value` is set only on create and is sensitive.
resource "vault_kv_secret_v2" "bifrost_hermes_key" {
  mount = var.secret_mount
  name  = "default/hermes/bifrost"
  data_json = jsonencode({
    API_KEY = bifrost_virtual_key.hermes.value
  })
  depends_on = [bifrost_virtual_key.hermes]
}

# Bifrost virtual key issued to Memex (its extraction/reflection/default models
# all route through Bifrost /v1). Stored under Memex's own KV prefix
# (default/memex/*) per the nomad-workloads role grant.
resource "vault_kv_secret_v2" "bifrost_memex_key" {
  mount = var.secret_mount
  name  = "default/memex/bifrost"
  data_json = jsonencode({
    API_KEY = bifrost_virtual_key.memex.value
  })
  depends_on = [bifrost_virtual_key.memex]
}

# Bifrost Postgres config_store credentials. The bifrost nomad-workloads role
# grants read on default/bifrost/*, so no policy change is needed.
resource "vault_kv_secret_v2" "bifrost_db_credentials" {
  mount = var.secret_mount
  name  = "default/bifrost/db"
  data_json = jsonencode({
    username = postgresql_role.role["bifrost"].name
    password = random_password.password["bifrost"].result
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
