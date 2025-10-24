resource "nomad_job" "postgres" {
    jobspec = templatefile("${path.module}/services/postgres.tftpl", { postgres_secret = vault_kv_secret_v2.postgres_root_credentials.path })
}
