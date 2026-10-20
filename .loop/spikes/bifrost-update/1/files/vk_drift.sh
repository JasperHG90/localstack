#!/usr/bin/env bash
# Spike: does AirHelp-OSP/bifrost provider VERSION create virtual keys shaped
# like bifrost_virtual_key.hermes on Bifrost IMAGE_TAG (Postgres config store,
# auth on) and then plan clean? Exit 0 only when apply succeeds and both
# follow-up plans (after create, after an in-place update) report no changes.
set -euo pipefail
PROVIDER_VERSION="${1:-0.1.1}"
IMAGE_TAG="${2:-v2.3.1}"
SCRATCH=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-1
WORK=$(mktemp -d "$SCRATCH/run.XXXX")
ID=spikebf$$
NET=$ID-net
PORT=$((18000 + $$ % 1000))
export TF_PLUGIN_CACHE_DIR="$SCRATCH/plugin-cache" CHECKPOINT_DISABLE=1 TF_IN_AUTOMATION=1
mkdir -p "$TF_PLUGIN_CACHE_DIR"
cleanup() {
  docker logs "$ID-bifrost" > "$WORK/bifrost.log" 2>&1 || true
  docker rm -f "$ID-bifrost" "$ID-pg" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
echo "provider=$PROVIDER_VERSION image=$IMAGE_TAG work=$WORK"

docker network create "$NET" >/dev/null
docker run -d --name "$ID-pg" --network "$NET" -e POSTGRES_USER=bifrost \
  -e POSTGRES_PASSWORD=pgpass -e POSTGRES_DB=bifrost postgres:16-alpine >/dev/null
for i in $(seq 1 30); do docker exec "$ID-pg" pg_isready -U bifrost -d bifrost >/dev/null 2>&1 && break; sleep 1; done

# Same providers and auth settings as services/bifrost.hcl, dummy key values.
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
      "network_config": {"base_url": "http://10.255.255.1:8000", "default_request_timeout_in_seconds": 60, "max_retries": 2, "allow_private_network": true},
      "custom_provider_config": {"base_provider_type": "openai", "allowed_requests": {"embedding": true, "rerank": true, "chat_completion": false, "chat_completion_stream": false, "text_completion": false, "speech": false, "transcription": false}}
    }
  },
  "config_store": {"enabled": true, "type": "postgres", "config": {"host": "$ID-pg", "port": "5432", "user": "bifrost", "password": "pgpass", "db_name": "bifrost", "ssl_mode": "disable"}},
  "logs_store": {"enabled": true, "type": "sqlite", "config": {"path": "/app/data/logs.db"}}
}
JSON
chmod 644 "$WORK/config.json"
docker create --name "$ID-bifrost" --network "$NET" -p "$PORT:8080" \
  -e APP_HOST=0.0.0.0 -e APP_PORT=8080 \
  -e BIFROST_ADMIN_USERNAME=admin -e BIFROST_ADMIN_PASSWORD=adminpass123 \
  -e OLLAMA_KEY_PERSONAL=dummy1 -e OLLAMA_KEY_XEBIA=dummy2 -e GEMINI_API_KEY=dummy3 -e EMBARK_API_KEY=dummy4 \
  "maximhq/bifrost:$IMAGE_TAG" >/dev/null
docker cp "$WORK/config.json" "$ID-bifrost:/app/data/config.json"
docker start "$ID-bifrost" >/dev/null
EP="http://127.0.0.1:$PORT"
for i in $(seq 1 60); do curl -fsS "$EP/health" >/dev/null 2>&1 && break; sleep 2; done
curl -fsS "$EP/health"; echo
echo "unauthenticated GET virtual-keys: $(curl -s -o /dev/null -w '%{http_code}' "$EP/api/governance/virtual-keys")"

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
output "hermes_value_set" { value = length(nonsensitive(bifrost_virtual_key.hermes.value)) > 0 }
TF
}

cd "$WORK"
write_tf 1
terraform init -no-color -input=false >/dev/null
terraform version -no-color | head -3
echo "== apply (create)"
terraform apply -no-color -input=false -auto-approve
echo "== state of hermes"
terraform state show -no-color bifrost_virtual_key.hermes | grep -v '"value"\|value  *=' || true
echo "== API view of virtual keys"
curl -s -u admin:adminpass123 "$EP/api/governance/virtual-keys" | head -c 3000; echo
echo "== plan 2 (after create)"
set +e
terraform plan -no-color -input=false -detailed-exitcode; P1=$?
set -e
echo "plan-after-create exit=$P1"
echo "== apply (in-place update: hermes gemini weight 1 -> 2)"
write_tf 2
set +e
terraform apply -no-color -input=false -auto-approve; A2=$?
terraform plan -no-color -input=false -detailed-exitcode; P2=$?
set -e
echo "update-apply exit=$A2 plan-after-update exit=$P2"
echo "== API view of hermes after update"
curl -s -u admin:adminpass123 "$EP/api/governance/virtual-keys" | head -c 3000; echo
if [ "$P1" = 0 ] && [ "$A2" = 0 ] && [ "$P2" = 0 ]; then echo RESULT: clean; exit 0; fi
echo RESULT: drift-or-error; exit 1
