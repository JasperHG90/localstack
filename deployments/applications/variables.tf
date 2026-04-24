variable "secret_mount" {
  description = "The mount path for the Vault KV secret engine"
  type        = string
}

variable "hermes_email_address" {
  description = "Gmail mailbox Hermes uses to send and receive mail (EMAIL_ADDRESS)"
  type        = string
}

variable "hermes_digest_email" {
  description = "Recipient address for the Memex weekly-digest cron"
  type        = string
}

variable "telegram_allowed_users" {
  description = "Telegram numeric user ID authorised to interact with the Hermes bot (also used as the home channel)"
  type        = string
}
