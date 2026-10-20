#!/usr/bin/env bash
# r3 for seaweedfs-cutover-observability: jobs healthy, SeaweedFS buckets
# growing across two readings, MinIO's flat, Grafana querying both stores'
# replacements, and the new dashboard and alert rules loaded.
set -euo pipefail
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
C=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/counts.sh
for j in loki tempo; do echo "## $j"; nomad job status $j | sed -n '/Latest Deployment/,/^$/p' | sed -n '3p'; done
echo "## reading 1"; $C loki tempo
sleep 120
echo "## reading 2"; $C loki tempo
GU="$(vault kv get -field=username secret/default/grafana/admin)"; GP="$(vault kv get -field=password secret/default/grafana/admin)"
G=https://grafana.lab.orangecluster.nl
now=$(date +%s); start=$((now - 600))
echo "## loki: log lines in the last 10 minutes, through Grafana"
curl -s -m 30 -u "$GU:$GP" -G "$G/api/datasources/proxy/uid/loki/loki/api/v1/query_range" \
  --data-urlencode 'query=sum(count_over_time({job=~".+"}[10m]))' --data-urlencode "start=$start" --data-urlencode "end=$now" --data-urlencode 'step=600' \
  | jq -r '.status, (.data.result[0].values[-1][1] // "none")'
echo "## tempo: traces in the last 10 minutes, through Grafana"
curl -s -m 30 -u "$GU:$GP" -G "$G/api/datasources/proxy/uid/tempo/api/search" \
  --data-urlencode "start=$start" --data-urlencode "end=$now" --data-urlencode 'limit=5' | jq -r '(.traces | length)'
echo "## dashboard"
curl -s -m 30 -u "$GU:$GP" "$G/api/dashboards/uid/localstack-seaweedfs" | jq -r '.dashboard.title, (.dashboard.panels | length)'
echo "## alert rules"
curl -s -m 30 -u "$GU:$GP" "$G/api/v1/provisioning/alert-rules" | jq -r '.[] | select(.uid | test("seaweedfs|scrape")) | "\(.uid) \(.title)"'
echo "## prometheus: seaweedfs alert states"
curl -s -m 30 -u "$GU:$GP" "$G/api/prometheus/grafana/api/v1/rules" | jq -r '.data.groups[].rules[] | select(.name | test("SeaweedFS|ScrapeJobMissing")) | "\(.name) \(.state) health=\(.health)"'
