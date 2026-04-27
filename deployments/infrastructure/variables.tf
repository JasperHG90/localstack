variable "secret_mount" {
  description = "The mount path for the Vault KV secret engine"
  type        = string
}

variable "gcp_project" {
  description = "GCP project ID for backup infrastructure"
  type        = string
}

variable "gcs_backup_bucket" {
  description = "GCS bucket name for off-site backups"
  type        = string
}

variable "telegram_alert_chat_id" {
  description = "Telegram chat ID that receives Grafana alerts (reuses Hermes bot token from Vault)."
  type        = string
  default     = "10650075"
}
