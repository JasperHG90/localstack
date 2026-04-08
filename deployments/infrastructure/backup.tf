### GCS backup bucket
resource "google_storage_bucket" "backups" {
  name                        = var.gcs_backup_bucket
  location                    = "europe-west4"
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type = "Delete"
    }
  }
}

### GCS service account
resource "google_service_account" "backup" {
  account_id   = "localstack-backup"
  display_name = "Localstack Backup"
}

resource "google_storage_bucket_iam_member" "backup_writer" {
  bucket = google_storage_bucket.backups.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backup.email}"
}

resource "google_service_account_key" "backup" {
  service_account_id = google_service_account.backup.name
}

### Vault secrets — credentials scoped per backup job
resource "vault_kv_secret_v2" "backup_postgres_db_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/backup-postgres/postgres"
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

resource "vault_kv_secret_v2" "backup_postgres_gcs_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/backup-postgres/gcs"
  data_json = jsonencode({
    service_account_json = base64decode(google_service_account_key.backup.private_key)
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

resource "vault_kv_secret_v2" "backup_minio_s3_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/backup-minio/minio"
  data_json = jsonencode({
    access_key = "minio"
    secret_key = random_password.minio_secret_key.result
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

resource "vault_kv_secret_v2" "backup_minio_gcs_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/backup-minio/gcs"
  data_json = jsonencode({
    service_account_json = base64decode(google_service_account_key.backup.private_key)
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = {
      managed_by = "terraform"
    }
  }
}

### Nomad backup jobs
resource "nomad_job" "backup_postgres" {
  jobspec = templatefile(
    "${path.module}/services/backup-postgres.hcl",
    {
      postgres_secret = vault_kv_secret_v2.backup_postgres_db_credentials.path
      gcs_secret      = vault_kv_secret_v2.backup_postgres_gcs_credentials.path
      postgres_host   = "192.168.2.30"
      gcs_bucket      = var.gcs_backup_bucket
    }
  )
}

resource "nomad_job" "backup_minio" {
  jobspec = templatefile(
    "${path.module}/services/backup-minio.hcl",
    {
      minio_secret = vault_kv_secret_v2.backup_minio_s3_credentials.path
      gcs_secret   = vault_kv_secret_v2.backup_minio_gcs_credentials.path
      minio_host   = "192.168.2.29"
      gcs_bucket   = var.gcs_backup_bucket
    }
  )
}
