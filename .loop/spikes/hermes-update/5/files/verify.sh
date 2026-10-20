#!/usr/bin/env bash
# r2 for hermes-update: run inside the live task over SSH and podman exec,
# because Nomad exec and alloc logs are refused on this client.
set -uo pipefail
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
echo "## deployment"; nomad job status hermes | sed -n '/Latest Deployment/,/^$/p' | sed -n '3,4p'
A=$(nomad job status hermes | awk '/^Allocations/{getline;getline;print $1;exit}')
nomad alloc status -stats "$A" | grep -A2 'Task "hermes"' | grep -oE "[0-9.]+ MiB/[0-9.]+ GiB" | head -1 | sed 's/^/hermes memory: /'
SSH="ssh -i .ssh/id_rsa -o BatchMode=yes -o ConnectTimeout=10 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR radxa@192.168.2.50"
$SSH "c=\$(sudo podman ps --format '{{.Names}}' | grep -E '^hermes-$A' | head -1); sudo podman image inspect \$(sudo podman inspect -f '{{.Image}}' \$c) --format 'image: {{index .RepoTags 0}}'; sudo podman exec -i \$c sh -s" <<'IN'
cd /opt/data
echo "## memory provider"; HERMES_HOME=/opt/data timeout 60 hermes memory status 2>&1 | grep -E 'Provider:|Plugin:|Status:'
grep version /opt/hermes/plugins/memory/openviking/plugin.yaml
echo "## search through the 1934 sidecar"
curl -s -m 60 -X POST http://127.0.0.1:1934/api/v1/search/find -H "Authorization: Bearer $OPENVIKING_API_KEY" -H 'Content-Type: application/json' -d '{"query":"engineering blog","limit":3}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("result") or {}; i=[x for k in ("memories","resources","skills") for x in (r.get(k) or [])]; print("status", d.get("status"), "hits", len(i)); [print(" ", x.get("uri")) for x in i[:3]]'
echo "## cron jobs"
python3 -c 'import json; d=json.load(open("/opt/data/cron/jobs.json")); [print(f"{j[\"name\"]:30} {j.get(\"state\") or (\"paused\" if j.get(\"paused\") else \"active\"):8} pinned={j.get(\"model\") or \"-\":8} last={j.get(\"last_run_at\")} {j.get(\"last_status\")}") for j in d["jobs"]]'
IN
