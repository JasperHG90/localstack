# developer-policy.hcl
# This policy grants permissions for development across all namespaces.

namespace "default" {
  policy = "write"
  capabilities = [
    "submit-job",
    "read-job",
    "list-jobs",
    "dispatch-job",
    "read-logs",
    "read-fs",
    "alloc-exec",
    "alloc-lifecycle",
    "alloc-node-exec"
  ]
}

# Grant full access to host volumes
host_volume "*" {
  policy = "write"
}

# Grant read-only access to cluster-level information needed for debugging.
node {
  policy = "read"
}
agent {
  policy = "read"
}
operator {
  policy = "read"
}
