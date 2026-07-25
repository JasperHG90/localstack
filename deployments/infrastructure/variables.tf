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
    ACME directory URL. Defaults to the STAGING endpoint on purpose:
    Let's Encrypt allows only 5 certificates per exact identifier set per 7
    days, so an over-issuing job locks out issuance for a week. Prove the job
    is idempotent first — run it twice against staging and confirm the
    certificate serial is unchanged — then flip to
    https://acme-v02.api.letsencrypt.org/directory. Staging and production
    keep separate account state, so the switch needs a fresh registration in
    the same --path.
  EOT
  type        = string
  default     = "https://acme-staging-v02.api.letsencrypt.org/directory"
}
