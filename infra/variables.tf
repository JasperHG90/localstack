variable "secret_mount" {
    description = "The mount path for the Vault KV secret engine"
    type        = string
}

variable "consul_address" {
  description = "The address of the Consul server"
  type        = string
}
