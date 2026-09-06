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

### registry-ui's OWN copy of the same registry credential, for the same
### reason embark needs one: the nomad-workloads role grants a job read only
### under secret/data/default/<job_id>/*, so job `registry-ui` reading
### default/registry/auth would 403. Read-only use — it lists repositories
### and reads manifests and small blobs; it never pushes.
resource "vault_kv_secret_v2" "registry_ui_credentials" {
  mount = var.secret_mount
  name  = "default/registry-ui/registry"
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

### OpenViking
###
### Split across two prefixes on purpose. What the JOB reads sits under
### default/openviking/*, the nomad-workloads role's grant (it allows a job
### read only on secret/data/<namespace>/<job_id>/*, so a path belonging to
### another job renders 403 and the task never starts) -- the same
### copy-under-the-consumer shape as bifrost_hermes_key and
### embark_registry_credentials. What the job must NOT read -- the seed and the
### humans' keys -- sits outside it, under default/openviking-seed/ and
### default/openviking-users/.

### The root key. It manages accounts and users through the Admin API and is
### what `auth_mode: "api_key"` authenticates ROOT against. It is NOT a human
### credential: people use their own per-user keys below.
resource "random_password" "openviking_root_key" {
  length  = 48
  special = false
}

### The seed every per-user key is derived from. One secret, so rotating it
### rotates every user key at once; the users themselves are unaffected.
resource "random_password" "openviking_user_seed" {
  length  = 48
  special = false
}

### The humans, and their keys.
###
### A key is NOT read back from the Admin API. OpenViking derives a seeded key
### as `sha256(user_id + NUL + seed)` wrapped in a base64url triple
### (`openviking/server/api_keys/new.py`, `legacy.py`), so Terraform computes
### the same value locally and the API call only has to REGISTER the user. That
### keeps the key in Vault and in state rather than in a response nobody kept,
### and makes `terraform apply` idempotent instead of minting a new key per run.
###
### The escape in the sha256 call below is a NUL byte, and it is load-bearing:
### it is the separator OpenViking joins on. Any other separator derives a key
### the server rejects, while `terraform apply` still succeeds and every gate
### stays green. Verified in both directions against the upstream code.
locals {
  openviking_account = "lab"
  openviking_users = {
    jasper = "admin"
    veerle = "user"
    # An agent, not a person. Its own key so its writes are attributable and
    # revoking it does not touch a human's.
    hermes = "user"
  }

  # The account's bootstrap admin, taken from the map rather than written a
  # second time in the provisioner: a literal there would survive that person
  # being removed from the map. Only POST /accounts takes one, and sort makes
  # the pick stable across runs; a second admin is legal and the provisioner's
  # role step promotes them. Zero admins fails here, which is the right answer:
  # the account cannot be created without one.
  openviking_admin_user = sort([for user, role in local.openviking_users : user if role == "admin"])[0]

  # base64url with ALL padding stripped, per segment. Two traps, each of which
  # yields a key that looks right and is rejected:
  #   - trimsuffix(x, "=") removes ONE "="; a 64-char hex secret encodes with
  #     TWO padding characters, so this must be replace, not trimsuffix.
  #   - Terraform's base64encode uses the standard alphabet while OpenViking
  #     uses URL-safe, so "+" and "/" have to be translated.
  openviking_b64url = {
    for k, v in merge(
      { account = local.openviking_account },
      { for user, _ in local.openviking_users : "user_${user}" => user },
      {
        for user, _ in local.openviking_users :
        "secret_${user}" => sha256("${user}\u0000${random_password.openviking_user_seed.result}")
      },
    ) : k => replace(replace(replace(base64encode(v), "=", ""), "+", "-"), "/", "_")
  }

  openviking_user_keys = {
    for user, _ in local.openviking_users :
    user => join(".", [
      local.openviking_b64url["account"],
      local.openviking_b64url["user_${user}"],
      local.openviking_b64url["secret_${user}"],
    ])
  }
}

resource "vault_kv_secret_v2" "openviking_root_key" {
  mount = var.secret_mount
  name  = "default/openviking/root"
  data_json = jsonencode({
    root_api_key = random_password.openviking_root_key.result
  })
}

### The seed is NOT in the resource above, and that is the whole point of this
### one. `default/openviking/*` is the prefix the nomad-workloads role grants
### the job, and seed + user_id derives any human's key offline, so a seed
### there would hand the service every key it must not hold. Nothing reads this
### path: the provisioner uses random_password directly and the job never wants
### it. It exists so an operator can re-derive a key by hand.
###
### Its own prefix rather than default/openviking-users/, where a person named
### `seed` in local.openviking_users would land on this exact path. Two
### resources writing one path is not an error in Vault, it is last-writer-wins
### and a diff that never settles.
resource "vault_kv_secret_v2" "openviking_seed" {
  mount = var.secret_mount
  name  = "default/openviking-seed/seed"
  data_json = jsonencode({
    seed = random_password.openviking_user_seed.result
  })
}

### One entry per human. Under `default/openviking-users/` for two reasons that
### both matter: the `developer` policy grants `secret/data/default/*`, so the
### deploying identity can write these, and the path sits OUTSIDE
### `default/openviking/*`, which is the prefix the nomad-workloads role grants
### the job. Vault's trailing glob is a literal prefix match, so
### `default/openviking-users/` is not covered by it and the service cannot
### read the humans' keys. This says nothing about person-to-person access:
### `developer` covers all of `default/*`, so anyone holding it reads everyone.
resource "vault_kv_secret_v2" "openviking_user_keys" {
  for_each = local.openviking_user_keys
  mount    = var.secret_mount
  name     = "default/openviking-users/${each.key}"
  data_json = jsonencode({
    account = local.openviking_account
    user    = each.key
    role    = local.openviking_users[each.key]
    api_key = each.value
  })
}

### Hermes's OpenViking key, copied under hermes's OWN KV prefix rather than
### read from default/openviking-users/hermes.
###
### The nomad-workloads role grants a job read on
### `secret/data/<namespace>/<job_id>/*` and nothing else, so job `hermes`
### reading an openviking-users path gets a 403, consul-template never renders,
### and the task never starts. Same reason bifrost_hermes_key and
### embark_registry_credentials above are copies under their consumers.
###
### The same derived key as the human entries, not a second one: the value
### comes from the same local, so one seed change still rotates every holder.
resource "vault_kv_secret_v2" "hermes_openviking_key" {
  mount = var.secret_mount
  name  = "default/hermes/openviking"
  data_json = jsonencode({
    account = local.openviking_account
    user    = "hermes"
    api_key = local.openviking_user_keys["hermes"]
  })
}

resource "vault_kv_secret_v2" "openviking_db_credentials" {
  mount = var.secret_mount
  name  = "default/openviking/db"
  data_json = jsonencode({
    username = postgresql_role.role["openviking"].name
    password = random_password.password["openviking"].result
  })
}

### The static MinIO key. OpenViking cannot use workload identity: its config
### layer makes access_key and secret_key mandatory for an s3 backend, and the
### Rust client behind AGFS drops the session token STS credentials require.
### Deliberately no minio_iam_policy named `openviking` in storage.tf, which
### would read as live while granting nothing.
resource "vault_kv_secret_v2" "openviking_minio_credentials" {
  mount = var.secret_mount
  name  = "default/openviking/minio"
  data_json = jsonencode({
    access_key = minio_accesskey.users["openviking"].access_key
    secret_key = minio_accesskey.users["openviking"].secret_key
  })
}

### The Bifrost virtual key OpenViking calls for embeddings and rerank.
resource "vault_kv_secret_v2" "bifrost_openviking_key" {
  mount = var.secret_mount
  name  = "default/openviking/bifrost"
  data_json = jsonencode({
    API_KEY = bifrost_virtual_key.openviking.value
  })
  depends_on = [bifrost_virtual_key.openviking]
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
