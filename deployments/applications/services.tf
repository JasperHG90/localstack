data "consul_service" "minio" {
    name = "minio"
    datacenter = "localstack"
}

data "consul_service" "postgres" {
    name = "postgres-db"
    datacenter = "localstack"
}

ephemeral "vault_kv_secret_v2" "minio_admin" {
  mount = "secret"
  name  = "default/minio/localstack"
}

ephemeral "vault_kv_secret_v2" "postgres_admin" {
  mount = "secret"
  name  = "default/postgres/localstack"
}
