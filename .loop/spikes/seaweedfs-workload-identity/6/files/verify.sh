#!/usr/bin/env bash
# Live checks for seaweedfs-workload-identity after the probe jobs ran.
set -euo pipefail
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
export AK="$(vault kv get -field=access_key secret/default/seaweedfs/admin)"
export SK="$(vault kv get -field=secret_key secret/default/seaweedfs/admin)"
export LOKI_AK="$(vault kv get -field=access_key secret/default/loki/seaweedfs)"
export LOKI_SK="$(vault kv get -field=secret_key secret/default/loki/seaweedfs)"
uv run --no-project --quiet --with boto3 python -I "$(dirname "$0")/check.py"
echo "## applications root plan with the IAM config loaded"
terraform -chdir=deployments/applications init -backend-config=./vars/backend-config.hcl -input=false >/dev/null
terraform -chdir=deployments/applications plan -var-file=./vars/prod.tfvars -input=false -no-color -detailed-exitcode | grep -E '^Plan:|No changes'
