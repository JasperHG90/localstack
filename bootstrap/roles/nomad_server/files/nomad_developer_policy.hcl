# developer-policy.hcl
# This policy grants permissions for development across all namespaces.

namespace "default" {
  policy = "write"
  capabilities = [
    "submit-job"
  ]
}

# Grant full access to host volumes
host_volume "*" {
  policy = "write"
}

# Grant full control over jobs (run, stop, read, etc.).
job {
  policy = "write"
}

# Grant ability to inspect allocations and read logs.
allocation {
  policy = "read"
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

# --- CRITICAL SECURITY RULE ---
# Explicitly DENY the ability to manage ACLs. This is what makes
# this token safer than the bootstrap token.
acl {
  policy = "deny"
}
