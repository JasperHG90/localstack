#!/usr/bin/env bash
# Live checks for seaweedfs-buckets, with keys read from Terraform state in memory.
set -euo pipefail
cd /home/vscode/workspace.worktrees/seaweedfs-buckets
eval "$(uv run localstack env)" 2>/dev/null
export AK="$(vault kv get -field=access_key secret/default/seaweedfs/admin)"
export SK="$(vault kv get -field=secret_key secret/default/seaweedfs/admin)"
terraform -chdir=deployments/applications show -json \
  | uv run --no-project --quiet --with boto3 python -I "$(dirname "$0")/check.py"
echo "## vault paths"
for p in loki tempo registry openviking backup-minio; do
  printf '%s/seaweedfs: ' "$p"; vault kv get -field=access_key "secret/default/$p/seaweedfs" >/dev/null && echo present
  printf '%s/minio: ' "$p"; vault kv get -field=access_key "secret/default/$p/minio" >/dev/null && echo present
done
