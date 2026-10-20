#!/usr/bin/env bash
# Spike: virtual keys created by AirHelp-OSP/bifrost PROVIDER on Bifrost FROM
# (Postgres config store, auth on), then Bifrost replaced by TO on the same
# database. Exit 0 only when, after the upgrade: plan reports no changes, every
# key still authenticates an inference call (and a bogus key does not), and an
# in-place update applies and plans clean.
set -euo pipefail
PROVIDER_VERSION="${1:-0.1.1}"
FROM="${2:-v2.0.0}"
TO="${3:-v2.3.1}"
SCRATCH=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-3
WORK=$(mktemp -d "$SCRATCH/run.XXXX")
ID=spikebfu$$
NET=$ID-net
PORT=$((19000 + $$ % 1000))
export TF_PLUGIN_CACHE_DIR="$SCRATCH/plugin-cache" CHECKPOINT_DISABLE=1 TF_IN_AUTOMATION=1
mkdir -p "$TF_PLUGIN_CACHE_DIR"
cleanup() {
  docker logs "$ID-bifrost" > "$WORK/bifrost-$TO.log" 2>&1 || true
  docker rm -f "$ID-bifrost" "$ID-pg" "$ID-stub" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
echo "provider=$PROVIDER_VERSION from=$FROM to=$TO work=$WORK"

docker network create "$NET" >/dev/null
docker run -d --name "$ID-pg" --network "$NET" -e POSTGRES_USER=bifrost \
  -e POSTGRES_PASSWORD=pgpass -e POSTGRES_DB=bifrost postgres:16-alpine >/dev/null
docker create --name "$ID-stub" --network "$NET" python:3.12-alpine python /stub.py >/dev/null
docker cp "$SCRATCH/stub.py" "$ID-stub:/stub.py"
docker start "$ID-stub" >/dev/null
STUBIP=$(docker inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" "$ID-stub")
for i in $(seq 1 30); do docker exec "$ID-pg" pg_isready -U bifrost -d bifrost >/dev/null 2>&1 && break; sleep 1; done

# Same providers and auth settings as services/bifrost.hcl, dummy key values;
# embark points at the stub.
cat > "$WORK/config.json" <<JSON
{
  "client": {"drop_excess_requests": false, "enable_logging": true, "enforce_auth_on_inference": true},
  "governance": {"auth_config": {"is_enabled": true, "admin_username": "env.BIFROST_ADMIN_USERNAME", "admin_password": "env.BIFROST_ADMIN_PASSWORD"}},
  "providers": {
    "ollama": {
      "keys": [
        {"name": "ollama-personal", "value": "env.OLLAMA_KEY_PERSONAL", "models": ["*"], "weight": 0.5, "ollama_key_config": {"url": "https://ollama.com"}},
        {"name": "ollama-xebia", "value": "env.OLLAMA_KEY_XEBIA", "models": ["*"], "weight": 0.5, "ollama_key_config": {"url": "https://ollama.com"}}
      ],
      "network_config": {"base_url": "https://ollama.com", "default_request_timeout_in_seconds": 120, "max_retries": 2}
    },
    "gemini": {"keys": [{"name": "gemini-primary", "value": "env.GEMINI_API_KEY", "models": ["*"], "weight": 1.0}]},
    "embark": {
      "keys": [{"name": "embark-cluster", "value": "env.EMBARK_API_KEY", "models": ["*"], "weight": 1.0}],
      "network_config": {"base_url": "http://$STUBIP:8000", "default_request_timeout_in_seconds": 60, "max_retries": 2, "allow_private_network": true},
      "custom_provider_config": {"base_provider_type": "openai", "allowed_requests": {"embedding": true, "rerank": true, "chat_completion": false, "chat_completion_stream": false, "text_completion": false, "speech": false, "transcription": false}}
    }
  },
  "config_store": {"enabled": true, "type": "postgres", "config": {"host": "$ID-pg", "port": "5432", "user": "bifrost", "password": "pgpass", "db_name": "bifrost", "ssl_mode": "disable"}},
  "logs_store": {"enabled": true, "type": "sqlite", "config": {"path": "/app/data/logs.db"}}
}
JSON
chmod 644 "$WORK/config.json"
EP="http://127.0.0.1:$PORT"

start_bifrost() {  # $1 = image tag
  docker create --name "$ID-bifrost" --network "$NET" -p "$PORT:8080" \
    -e APP_HOST=0.0.0.0 -e APP_PORT=8080 \
    -e BIFROST_ADMIN_USERNAME=admin -e BIFROST_ADMIN_PASSWORD=adminpass123 \
    -e OLLAMA_KEY_PERSONAL=dummy1 -e OLLAMA_KEY_XEBIA=dummy2 -e GEMINI_API_KEY=dummy3 -e EMBARK_API_KEY=dummy4 \
    "maximhq/bifrost:$1" >/dev/null
  docker cp "$WORK/config.json" "$ID-bifrost:/app/data/config.json"
  docker start "$ID-bifrost" >/dev/null
  for i in $(seq 1 60); do curl -fsS "$EP/health" >/dev/null 2>&1 && break; sleep 2; done
  echo "health on $1: $(curl -fsS "$EP/health")"
}

infer() {  # $1 = virtual key value; prints HTTP status of an embeddings call
  curl -s -o "$WORK/infer.out" -w '%{http_code}' -H "x-bf-vk: $1" -H 'content-type: application/json' \
    -d '{"model":"embark/embedding","input":"probe"}' "$EP/v1/embeddings"
}

write_tf() {  # $1 = weight of the hermes gemini entry
cat > "$WORK/main.tf" <<TF
terraform {
  required_providers {
    bifrost = { source = "AirHelp-OSP/bifrost", version = "$PROVIDER_VERSION" }
  }
}
provider "bifrost" {
  endpoint = "$EP"
  username = "admin"
  password = "adminpass123"
}
resource "bifrost_virtual_key" "hermes" {
  name = "hermes"
  provider_configs = [
    { provider = "embark", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = $1 },
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]
}
resource "bifrost_virtual_key" "memex" {
  name = "memex"
  provider_configs = [
    { provider = "embark", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]
}
resource "bifrost_virtual_key" "openviking" {
  name = "openviking"
  provider_configs = [
    { provider = "embark", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]
}
output "values" {
  value     = { for k, v in { hermes = bifrost_virtual_key.hermes, memex = bifrost_virtual_key.memex, openviking = bifrost_virtual_key.openviking } : k => v.value }
  sensitive = true
}
TF
}

infer_all() {  # $1 = label; sets FAILS
  for k in hermes memex openviking; do
    v=$(terraform output -json values | python3 -c "import json,sys; print(json.load(sys.stdin)['$k'])")
    s=$(infer "$v")
    echo "$1 inference $k: HTTP $s $(head -c 200 "$WORK/infer.out")"
    [ "$s" = 200 ] || FAILS=$((FAILS + 1))
  done
  s=$(infer sk-bf-00000000-bogus)
  echo "$1 inference bogus key: HTTP $s"
  [ "$s" != 200 ] || FAILS=$((FAILS + 1))
}

cd "$WORK"
FAILS=0
start_bifrost "$FROM"
write_tf 1
terraform init -no-color -input=false >/dev/null
terraform version -no-color | head -1
echo "== apply (create) on $FROM"
terraform apply -no-color -input=false -auto-approve
set +e
terraform plan -no-color -input=false -detailed-exitcode >/dev/null; P0=$?
set -e
echo "plan on $FROM after create exit=$P0"
infer_all "$FROM"
echo "== API view on $FROM"
curl -s -u admin:adminpass123 "$EP/api/governance/virtual-keys" | head -c 1500; echo
PRE_FAILS=$FAILS

echo "== upgrade: stop $FROM, start $TO on the same Postgres"
docker logs "$ID-bifrost" > "$WORK/bifrost-$FROM.log" 2>&1 || true
docker rm -f "$ID-bifrost" >/dev/null
start_bifrost "$TO"
echo "== API view on $TO"
curl -s -u admin:adminpass123 "$EP/api/governance/virtual-keys" | head -c 1500; echo
echo "== plan on $TO (refresh of $FROM state)"
set +e
terraform plan -no-color -input=false -detailed-exitcode; P1=$?
set -e
echo "plan after upgrade exit=$P1"
FAILS=0
infer_all "$TO"
INF_FAILS=$FAILS
echo "== in-place update on $TO: hermes gemini weight 1 -> 2"
write_tf 2
set +e
terraform apply -no-color -input=false -auto-approve; A2=$?
terraform plan -no-color -input=false -detailed-exitcode >/dev/null; P2=$?
set -e
echo "update-apply exit=$A2 plan-after-update exit=$P2"
FAILS=0
infer_all "$TO after update"
echo "== API view of hermes after update"
curl -s -u admin:adminpass123 "$EP/api/governance/virtual-keys" | python3 -c "import json,sys; d=json.load(sys.stdin); [print(json.dumps(v.get('provider_configs'))) for v in d.get('virtual_keys',[]) if v.get('name')=='hermes']" || true
echo "SUMMARY pre_fails=$PRE_FAILS plan0=$P0 plan_after_upgrade=$P1 infer_fails_after_upgrade=$INF_FAILS update_apply=$A2 plan_after_update=$P2 infer_fails_after_update=$FAILS"
if [ "$P1" = 0 ] && [ "$INF_FAILS" = 0 ] && [ "$A2" = 0 ] && [ "$P2" = 0 ] && [ "$FAILS" = 0 ]; then echo RESULT: clean; exit 0; fi
echo RESULT: drift-or-error; exit 1
