#!/usr/bin/env bash
# Validate every Terraform root offline (no remote state, no credentials).
# Only initialize a root that has no provider schemas yet; init -backend=false
# pulls providers only. Already-initialized roots validate directly, so we
# never touch the Consul backend.
set -euo pipefail

roots=(
  deployments/infrastructure
  deployments/applications
  deployments/applications/modules/bucket
)

for d in "${roots[@]}"; do
  echo "==> terraform validate ${d}"
  if [ ! -d "${d}/.terraform" ]; then
    terraform -chdir="${d}" init -backend=false -input=false -no-color >/dev/null
  fi
  terraform -chdir="${d}" validate -no-color
done
