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
  description = <<-EOT
    Telegram chat that receives Grafana alerts. The value is the operator's own
    numeric user ID, which is also the id of their private chat with
    OrangeClusterAlertBot, so it survives a bot swap unchanged.

    It is that bot's entire outbound scope: Grafana writes to this chat and no
    other, so nobody else receives an alert. Inbound is not scoped here at all,
    because nothing reads the bot's updates. See "Where alerts go" in
    docs/monitoring.md.
  EOT
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

variable "vault_operator_email" {
  description = "Email address published as the operator entity's `email` claim. Grafana refuses an SSO login whose resolved email is empty, so this is load-bearing rather than descriptive."
  type        = string
  default     = "jasperginn@gmail.com"
}

variable "vault_operator_ov_identity" {
  description = "The operator's OpenViking identity: which account, and which user inside it. Two values because they differ. The account is `lab`, which everyone shared before OV2 split them; OV2 created the per-person accounts and migrated nothing, so the content is still in `lab`. The user is `jasper`, because the tree is at `lab/user/jasper` and there is no `lab/user/lab`. Neither is the Vault entity name: that entity is a cluster-admin identity and these are data identities."
  type = object({
    account = string
    user    = string
  })
  default = {
    account = "lab"
    user    = "jasper"
  }
}

variable "vault_openviking_consumers" {
  description = "People who use OpenViking and nothing else on this cluster, keyed by username. Each gets a userpass login, an entity carrying `ov_account`, and membership of the `openviking-user` group, whose policy grants exactly one Vault path. They are in no other group, so no Grafana, no Nomad UI, no MinIO console and no localstack CLI. The key is the username and the entity name. The account and user are separate because they differ: everyone shares the `lab` account, and the user inside it is what isolates one person's tree from another's while `viking://resources` stays common. `email` is optional and only feeds the OIDC provider's `email` scope, which a consumer has no client to use."
  type = map(object({
    account = string
    user    = string
    email   = optional(string)
  }))
  default = {
    veerle = {
      account = "lab"
      user    = "veerle"
    }
  }
}

variable "oidc_smoke_redirect_uris" {
  description = "Redirect URIs for F2's throwaway smoke-test OIDC client. A placeholder is fine: the client exists to prove the issuer completes an auth-code flow, not to serve a real app. Consumer tickets set their own. WARNING: the default hardcodes the issuer host, because Terraform forbids interpolation in a default. Change vault_issuer_host and this must be changed with it, or the redirect silently stops matching."
  type        = list(string)
  default     = ["https://vault.lab.orangecluster.nl/ui/vault/auth/oidc/oidc/callback"]
}

variable "vault_openviking_workloads" {
  description = "Nomad jobs that reach OpenViking, keyed by job id. The key IS the alias name Vault's jwt-nomad mount creates, because that role sets `user_claim = /nomad_job_id`. The value is the account and the user the job writes as: hermes gets `lab`/`jasper`, its principal's tree, because OpenViking grants no cross-user read and an assistant with its own user could not see the scope it works for. Each entry mints one identity-token role (oidc.tf) whose read is granted by one policy on that job's own JWT role (machine_roles.tf)."
  type = map(object({
    account = string
    user    = string
  }))
  default = {
    hermes = {
      account = "lab"
      user    = "jasper"
    }
  }
}
