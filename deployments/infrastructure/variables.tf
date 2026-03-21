variable "secret_mount" {
    description = "The mount path for the Vault KV secret engine"
    type        = string
}

variable "node_ids" {
    description = "Map of hostname to Nomad node ID"
    type        = map(string)
}
