#!/usr/bin/env bash
# r3 for bifrost-update: smoke script, bare-string rerank via OpenViking's key,
# request rate after the switch, and a clean second plan.
set -uo pipefail
W=/home/vscode/workspace.worktrees/bifrost-update
cd "$W"
eval "$(uv run localstack env)" 2>/dev/null
echo "## deployment"; nomad job status bifrost | sed -n '/Latest Deployment/,/^$/p' | sed -n '3p'
nomad job status bifrost | grep -m1 -oE 'bifrost:v[0-9.]+' || nomad job inspect bifrost | grep -oE 'bifrost:v[0-9.]+' | head -1
echo "## smoke"; python3 -I scripts/bifrost_smoke.py --base-url http://192.168.2.50:8080; echo "smoke exit $?"
echo "## bare-string rerank through the OpenViking key"
K="$(vault kv get -field=API_KEY secret/default/openviking/bifrost)"
curl -s -m 60 -o /tmp/rr.json -w 'http %{http_code}\n' -X POST http://192.168.2.50:8080/v1/rerank -H "x-bf-vk: $K" -H 'Content-Type: application/json' \
  -d '{"model":"embark/reranker","query":"capital of France","documents":["Paris is the capital of France","bananas are yellow"]}'
python3 -I -c "import json; d=json.load(open('/tmp/rr.json')); print('results:', [(r.get('index'), round(r.get('relevance_score', 0), 3)) for r in d.get('results', [])])"; rm -f /tmp/rr.json
echo "## request rate after the switch (Prometheus via Grafana)"
GU="$(vault kv get -field=username secret/default/grafana/admin)"; GP="$(vault kv get -field=password secret/default/grafana/admin)"
curl -s -m 20 -u "$GU:$GP" -G https://grafana.lab.orangecluster.nl/api/datasources/proxy/uid/prometheus/api/v1/query \
  --data-urlencode 'query=sum(increase(bifrost_upstream_requests_total[10m])) + sum(increase(bifrost_success_requests_total[10m]))' | python3 -I -c "import json,sys; r=json.load(sys.stdin)['data']['result']; print('requests in last 10m:', r[0]['value'][1] if r else 'none')"
echo "## second plan"
terraform -chdir=deployments/applications plan -var-file=./vars/prod.tfvars -input=false -no-color 2>&1 | grep -E '^Plan:|No changes|^  # [a-z]' | sed 's/^  # //'
