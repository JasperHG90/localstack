### Off-cluster object storage. Today that is one GCS bucket: the destination
### the backup jobs in services.tf write to. On-cluster MinIO buckets are the
### applications root's (deployments/applications/storage.tf).

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
