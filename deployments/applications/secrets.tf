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

### embark
###
### embark ships auth ON and refuses to start when it is enabled with no keys,
### so this is a precondition for the job, not a hardening step. One `read`
### key for cluster callers; embark also supports JWT via JWKS, which would let
### it verify Nomad workload identities the way memex does, but that is a
### bigger change than standing the service up.
resource "random_id" "embark_api_key" {
  byte_length = 32
}

resource "vault_kv_secret_v2" "embark_auth" {
  mount = var.secret_mount
  name  = "default/embark/auth"
  data_json = jsonencode({
    api_key = random_id.embark_api_key.b64_url
  })
}

### The registry credential embark's model-pull task reads, copied under
### embark's OWN KV prefix rather than read from default/registry/auth.
###
### The nomad-workloads role grants a job read on
### `secret/data/<namespace>/<job_id>/*` and nothing else
### (bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2), so
### job `embark` reading the registry's own path gets a 403 and the prestart
### task never renders. Same reason bifrost_hermes_key and bifrost_memex_key
### above are copies under their consumers' prefixes.
###
### Same values as vault_kv_secret_v2.registry_auth, minus the htpasswd hash:
### a puller needs the plaintext password, never the server's hash.
resource "vault_kv_secret_v2" "embark_registry_credentials" {
  mount = var.secret_mount
  name  = "default/embark/registry"
  data_json = jsonencode({
    username = "push"
    password = random_password.registry_push.result
  })
}

### embark's API key, copied under Bifrost's OWN KV prefix so Bifrost can call
### embark as a provider. embark ships auth on, and the nomad-workloads role
### grants job `bifrost` read only under secret/data/default/bifrost/*, so
### reading default/embark/auth would 403. Same copy-under-the-consumer shape
### as embark_registry_credentials above, in the other direction: the other
### bifrost_*_key secrets are keys Bifrost ISSUES, this one is a key it USES.
resource "vault_kv_secret_v2" "bifrost_embark_key" {
  mount = var.secret_mount
  name  = "default/bifrost/embark"
  data_json = jsonencode({
    API_KEY = random_id.embark_api_key.b64_url
  })
}

### Registry

resource "vault_kv_secret_v2" "registry_minio_credentials" {
  mount = var.secret_mount
  name  = "default/registry/minio"
  data_json = jsonencode({
    access_key = minio_accesskey.users["registry"].access_key
    secret_key = minio_accesskey.users["registry"].secret_key
  })
}

### The registry's push/pull credential. `bcrypt_hash` is a computed
### attribute the random provider generates ONCE and keeps in state, unlike
### the `bcrypt()` function, which re-salts on every plan and would rewrite
### this secret (and restart the registry) on every apply.
###
### The registry reads htpasswd as a FILE at startup, so it cannot consume
### Vault dynamic credentials: rotating this means tainting the resource and
### letting the job restart. That is a deliberate step back from the
### short-lived-credential direction the rest of the cluster is moving in,
### accepted because the OCI distribution spec offers only htpasswd or a
### Docker-specific token server, and no OIDC.
resource "random_password" "registry_push" {
  length  = 32
  special = false
}

resource "vault_kv_secret_v2" "registry_auth" {
  mount = var.secret_mount
  name  = "default/registry/auth"
  data_json = jsonencode({
    username = "push"
    password = random_password.registry_push.result
    htpasswd = "push:${random_password.registry_push.bcrypt_hash}"
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
