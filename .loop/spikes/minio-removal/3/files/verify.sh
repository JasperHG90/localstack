#!/usr/bin/env bash
# r2 and r3 for minio-removal: state and plans clean, jobs gone, backup-s3 runs.
set -euo pipefail
W=/home/vscode/workspace.worktrees/minio-removal
cd "$W"
eval "$(uv run localstack env)" 2>/dev/null
echo "## applications state: minio_ or module.buckets addresses"
terraform -chdir=deployments/applications state list | grep -cE '^(minio_|module\.buckets)' || true
for r in applications infrastructure; do
  echo "## $r plan"
  terraform -chdir=deployments/$r plan -var-file=./vars/prod.tfvars -input=false -no-color -detailed-exitcode 2>&1 \
    | grep -E 'No changes|^Plan:|  # ' | grep -v 'null_resource.firewall' || true
done
echo "## nomad"
for j in minio backup-minio; do printf '%s: ' "$j"; nomad job status "$j" 2>&1 | head -1; done
printf 'backup-s3 forced run (periodic-1792486100, alloc 91b5d9d2): '; nomad alloc status 91b5d9d2 | grep 'Exit Code' | tr -s ' '
printf 'ov-dash: '; nomad job status ov-dash | sed -n '/Latest Deployment/,/^$/p' | sed -n '3p'
printf 'ov-dash route: '; curl -s -m 15 -o /dev/null -w '%{http_code}\n' https://openviking.lab.orangecluster.nl/
echo "## vault: old MinIO key paths"
for p in default/minio/localstack default/backup-minio/minio default/backup-minio/gcs default/backup-minio/seaweedfs default/loki/minio; do
  printf '%s: ' "$p"; vault kv get "secret/$p" >/dev/null 2>&1 && echo present || echo gone
done
