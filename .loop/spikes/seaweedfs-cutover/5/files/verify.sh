#!/usr/bin/env bash
# r4 for seaweedfs-cutover: the backup from SeaweedFS matches GCS, the s3
# route and edge serve SeaweedFS, and MinIO's counts stay fixed.
set -euo pipefail
D="$(dirname "$0")"
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
echo "## first backup from SeaweedFS: backup-minio/periodic-1792483971, alloc d12af9d8"
nomad alloc status d12af9d8 | grep -E 'Exit Code'
echo "## SeaweedFS against GCS after that run"
SW_AK="$(vault kv get -field=access_key secret/default/seaweedfs/admin)" SW_SK="$(vault kv get -field=secret_key secret/default/seaweedfs/admin)" \
GCS_SA_JSON="$(vault kv get -field=service_account_json secret/default/backup-minio/gcs)" \
  uv run --no-project --quiet --with boto3 --with google-cloud-storage python -I "$D/after.py"
echo "## the CLI's s3 route"
uv run localstack service 2>&1 | grep -E '│ s3 '
echo "## s3.lab"
curl -s -m 15 -o /dev/null -D - https://s3.lab.orangecluster.nl/ | grep -iE '^server'
echo "## MinIO counts: reading 1 at 08:12:58 UTC was openviking 45765, registry 399, loki 13581, tempo 6502, models 0, datalake 0"
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/counts.sh openviking registry loki tempo models datalake
