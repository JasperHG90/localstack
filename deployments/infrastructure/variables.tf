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

variable "acme_domain" {
  description = "Lab zone the ACME wildcard covers. lego is asked for both *.<domain> and <domain>, since a wildcard does not match the bare name."
  type        = string
  default     = "lab.orangecluster.nl"
}

variable "acme_email" {
  description = "Registration address for the Let's Encrypt ACME account (expiry notices)."
  type        = string
  default     = "jasperginn@gmail.com"
}

variable "acme_server" {
  description = <<-EOT
    ACME directory URL. Production, since the staging gate has been cleared:
    the job was run twice against the staging endpoint and lego reported
    "Skip renewal" with an unchanged certificate serial, proving it does not
    re-issue on every run. That mattered because Let's Encrypt allows only 5
    certificates per exact identifier set per 7 days, and an over-issuing job
    locks out issuance for a week.

    Point this back at https://acme-staging-v02.api.letsencrypt.org/directory
    to test changes to the job. State is namespaced by environment, so the two
    keep separate accounts and certificates and a staging leaf can never
    satisfy a production run's not-due check.
  EOT
  type        = string
  default     = "https://acme-v02.api.letsencrypt.org/directory"
}
