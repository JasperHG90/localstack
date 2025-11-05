variable name {
    description = "The name of the bucket to create."
    type        = string
}

variable acl {
    description = "The ACL to apply to the bucket."
    type        = string
    default     = "private"
}

variable permissions {
    description = "MinIO IAM users to grant either read or read + write access to the bucket."
    type        = object({
        readers = list(string)
        writers = list(string)
    })
    default = {
        readers = []
        writers = []
    }
}
