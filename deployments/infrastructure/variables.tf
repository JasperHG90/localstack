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

variable "vault_issuer_host" {
  description = "Host the Vault OIDC provider advertises as its issuer. Baked into every issued token and into each consumer's client config, so changing it later means re-issuing everywhere. Uses the edge hostname, not the backend IP, so it survives a backend change."
  type        = string
  default     = "vault.lab.orangecluster.nl"
}

variable "vault_operator_username" {
  description = "Username for the human userpass account whose entity OIDC assignments gate on. The password is generated and written to Vault KV2; it is never set here."
  type        = string
  default     = "operator"
}

variable "oidc_smoke_redirect_uris" {
  description = "Redirect URIs for F2's throwaway smoke-test OIDC client. A placeholder is fine: the client exists to prove the issuer completes an auth-code flow, not to serve a real app. Consumer tickets set their own. WARNING: the default hardcodes the issuer host, because Terraform forbids interpolation in a default. Change vault_issuer_host and this must be changed with it, or the redirect silently stops matching."
  type        = list(string)
  default     = ["https://vault.lab.orangecluster.nl/ui/vault/auth/oidc/oidc/callback"]
}
