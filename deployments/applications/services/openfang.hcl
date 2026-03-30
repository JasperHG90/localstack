job "openfang" {
  datacenters = ["localstack"]
  type        = "service"

  group "openfang" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${openfang_hostname}"
    }

    volume "openfang_data_volume" {
      type            = "host"
      source          = "openfang_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    network {
      port "http" {
        static = 50051
      }
    }

    task "openfang" {
      driver = "podman"

      volume_mount {
        volume      = "openfang_data_volume"
        destination = "/data"
      }

      service {
        name    = "openfang"
        port    = "http"
        address = "${openfang_host}"

        tags = ["http", "openfang", "agents"]

        check {
          type     = "http"
          path     = "/api/health"
          interval = "10s"
          timeout  = "2s"
        }
      }

      vault {}

      template {
        data = <<EOF
{{- with secret "${memex_auth_secret}" }}
MEMEX_API_KEY={{ .Data.data.admin_key }}
{{- end }}
{{- with secret "${github_secret}" }}
GIT_AUTH_TOKEN={{ .Data.data.pat }}
{{- end }}
{{- with secret "${telegram_secret}" }}
TELEGRAM_BOT_TOKEN={{ .Data.data.bot_token }}
{{- end }}
{{- with secret "${minimax_secret}" }}
MINIMAX_API_KEY={{ .Data.data.api_key }}
{{- end }}
{{- with secret "${openrouter_secret}" }}
OPENROUTER_API_KEY={{ .Data.data.api_key }}
{{- end }}
{{- with secret "${nomad_secret}" }}
NOMAD_TOKEN={{ .Data.data.token }}
{{- end }}
{{- with secret "${openfang_minio_secret}" }}
MEMEX_S3_ACCESS_KEY={{ .Data.data.access_key }}
MEMEX_S3_SECRET_KEY={{ .Data.data.secret_key }}
{{- end }}
EOF

        destination = "secrets/file.env"
        env         = true
      }

      env {
        OPENFANG_LISTEN   = "0.0.0.0:50051"
        MEMEX_SERVER_URL  = "http://${memex_host}:8000"
        MEMEX_S3_ENDPOINT = "http://${minio_host}:9000"
        MEMEX_S3_BUCKET   = "memex"
        MEMEX_S3_REGION   = "us-east-1"
      }

      template {
        data = <<EOF
[default_model]
provider = "openrouter"
model = "openrouter/google/gemini-3-flash-preview"
api_key_env = "OPENROUTER_API_KEY"

[channels.telegram]
bot_token_env = "TELEGRAM_BOT_TOKEN"
allowed_users = [${join(", ", telegram_allowed_users)}]

EOF

        destination = "local/config.toml"
      }

      template {
        data = <<EOF
[
  {
    "id": "openrouter/google/gemini-3-flash-preview",
    "display_name": "Gemini 3 Flash Preview (OpenRouter)",
    "provider": "openrouter",
    "tier": "Custom",
    "context_window": 1000000,
    "max_output_tokens": 65536,
    "input_cost_per_m": 0.0,
    "output_cost_per_m": 0.0,
    "supports_tools": true,
    "supports_vision": true,
    "supports_streaming": true,
    "aliases": []
  },
  {
    "id": "openrouter/mistralai/mistral-small-2603",
    "display_name": "Mistral Small 2603 (OpenRouter)",
    "provider": "openrouter",
    "tier": "Custom",
    "context_window": 128000,
    "max_output_tokens": 8192,
    "input_cost_per_m": 0.0,
    "output_cost_per_m": 0.0,
    "supports_tools": true,
    "supports_vision": false,
    "supports_streaming": true,
    "aliases": []
  }
]
EOF

        destination = "local/custom_models.json"
      }

      template {
        data = <<EOF
#!/bin/sh
# Entrypoint: start OpenFang, wait for boot, push vault secrets.
# Skills, agents, and hands auto-load from SQLite on boot.
# Registration of new resources happens via sync_openfang (register.sh).

openfang start &
PID=$!

# Wait for API to be ready
attempts=0
while [ $attempts -lt 30 ]; do
  curl -sf http://127.0.0.1:50051/api/health > /dev/null 2>&1 && break
  attempts=$((attempts + 1))
  sleep 2
done

# Give SQLite auto-load time to finish
sleep 3

# Push secrets to OpenFang credential vault
{{- with secret "${nomad_secret}" }}
watchdog_id=`openfang agent list 2>/dev/null | grep "cluster-watchdog-hand" | awk '{print $1}' | head -1`
if [ -n "$watchdog_id" ]; then
  curl -sf -X PUT "http://127.0.0.1:50051/api/memory/agents/$watchdog_id/kv/NOMAD_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"value": "{{ .Data.data.token }}"}' || true
  echo "entrypoint: pushed NOMAD_TOKEN to vault for agent $watchdog_id"
else
  echo "entrypoint: cluster-watchdog-hand not found, skipping vault push"
fi
{{- end }}

wait $PID
EOF

        destination = "local/entrypoint.sh"
        perms       = "0755"
      }

      config {
        volumes = [
          "local/config.toml:/data/config.toml",
          "local/custom_models.json:/data/custom_models.json",
          "local/entrypoint.sh:/tmp/entrypoint.sh",
        ]
        image        = "ghcr.io/jasperhg90/openfang:${openfang_version}"
        force_pull   = true
        network_mode = "host"
        command      = "/bin/sh"
        args         = ["/tmp/entrypoint.sh"]
      }

      resources {
        cpu    = 6000
        memory = 2800
      }
    }
  }
}
