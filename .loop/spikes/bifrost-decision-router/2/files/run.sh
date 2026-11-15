#!/usr/bin/env bash
# Spike bifrost-decision-router risk 1: Bifrost 2.3.1 with
# governance.complexity_analyzer_config (classifier decision, ollama/clef:cloud)
# and global routing_rules on virtual_key_name + complexity_tier from
# config.json, split mode, Postgres store, auth on. Upstream is a mock Ollama.
set -u
S=/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf1
N=spikebfdr
cleanup() { docker rm -f $N-bf $N-mock $N-pg >/dev/null 2>&1; docker network rm $N >/dev/null 2>&1; }
trap cleanup EXIT
cleanup
docker network create $N >/dev/null
docker run -d --name $N-pg --network $N -e POSTGRES_USER=bifrost -e POSTGRES_PASSWORD=bifrost -e POSTGRES_DB=bifrost postgres:16-alpine >/dev/null
docker create --name $N-mock --network $N -p 127.0.0.1:18434:11434 python:3.12-alpine python -u /mock.py >/dev/null
docker cp "$S/mock.py" $N-mock:/mock.py
docker start $N-mock >/dev/null
for i in $(seq 1 30); do docker exec $N-pg pg_isready -U bifrost >/dev/null 2>&1 && break; sleep 1; done
ip() { docker inspect -f "{{(index .NetworkSettings.Networks \"$N\").IPAddress}}" "$1"; }
sed -e "s/MOCKIP/$(ip $N-mock)/g" -e "s/PGIP/$(ip $N-pg)/g" "$S/config.json" > "$S/config.rendered.json"
docker create --name $N-bf --network $N -p 127.0.0.1:18080:8080 -e BIFROST_ADMIN_USERNAME=admin \
  -e BIFROST_ADMIN_PASSWORD=spikepass123 -e OLLAMA_KEY_PERSONAL=mockkey maximhq/bifrost:v2.3.1 >/dev/null
docker cp "$S/config.rendered.json" $N-bf:/app/data/config.json
docker start $N-bf >/dev/null
for i in $(seq 1 60); do curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break; sleep 1; done
echo "health: $(curl -sS http://127.0.0.1:18080/health)"
python3 "$S/client.py" http://127.0.0.1:18080 http://127.0.0.1:18434
rc=$?
echo "=== bifrost log (complexity/routing/rule/error lines) ==="
docker logs $N-bf 2>&1 | grep -v migration | grep -iE "complexity|routing rule|decision|error|fatal" | head -40
exit $rc
