#!/usr/bin/env bash
# Live checks for seaweedfs-service: deployment health, S3, LAN ports, Prometheus, MinIO untouched.
set -euo pipefail
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
echo "## seaweedfs deployment (healthy means its Consul check passed)"
nomad job status seaweedfs | sed -n '/Latest Deployment/,/^$/p;/^Deployed/,/^$/p;/^Allocations/,$p'
echo "## minio job (unchanged: version and running alloc)"
nomad job status minio | sed -n '/^Allocations/,$p'
echo "## s3 and ports"
AK="$(vault kv get -field=access_key secret/default/seaweedfs/admin)" SK="$(vault kv get -field=secret_key secret/default/seaweedfs/admin)" \
  uv run --no-project --quiet --with boto3 python -I "$(dirname "$0")/s3check.py"
echo "## prometheus, through grafana's datasource proxy"
GU="$(vault kv get -field=username secret/default/grafana/admin)"
GP="$(vault kv get -field=password secret/default/grafana/admin)"
curl -s -m 20 -u "$GU:$GP" -G https://grafana.lab.orangecluster.nl/api/datasources/proxy/uid/prometheus/api/v1/query \
  --data-urlencode 'query=up{job=~"seaweedfs|minio"}' \
  | jq -e -r '.data.result[]|"\(.metric.job) \(.metric.instance) up=\(.value[1])"' | tee /dev/stderr | grep -q 'seaweedfs .* up=1'
