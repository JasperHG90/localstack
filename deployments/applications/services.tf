data "consul_service" "minio" {
    name = "minio"
    # Optional parameter: implicitly uses the current datacenter of the agent
    datacenter = "localstack"
}

ephemeral "vault_kv_secret_v2" "db_secret" {
  mount = "secret"
  name  = "default/minio/localstack"
}
