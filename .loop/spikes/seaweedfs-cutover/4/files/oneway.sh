#!/usr/bin/env bash
# Run the one-way GCS-to-SeaweedFS check with keys from Vault, in memory.
set -euo pipefail
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
export SW_AK="$(vault kv get -field=access_key secret/default/seaweedfs/admin)" SW_SK="$(vault kv get -field=secret_key secret/default/seaweedfs/admin)"
export GCS_SA_JSON="$(vault kv get -field=service_account_json secret/default/backup-minio/gcs)"
uv run --no-project --quiet --with boto3 --with google-cloud-storage python -I "$(dirname "$0")/oneway.py"
