#!/usr/bin/env bash
# A listing-only MinIO-to-GCS comparison.
set -euo pipefail
cd /home/vscode/workspace
eval "$(uv run localstack env)"
export MINIO_AK="$(vault kv get -field=access_key secret/default/backup-minio/minio)"
export MINIO_SK="$(vault kv get -field=secret_key secret/default/backup-minio/minio)"
export GCS_SA_JSON="$(vault kv get -field=service_account_json secret/default/backup-minio/gcs)"
uv run --no-project --quiet --with google-cloud-storage --with boto3 python -I "$(dirname "$0")/compare.py"
