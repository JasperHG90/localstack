job "bifrost" {
  datacenters = ["localstack"]
  type        = "service"

  group "bifrost" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${bifrost_hostname}"
    }

    network {
      port "http" {
        static = 8080
      }
    }

    task "bifrost" {
      driver = "podman"

      service {
        name    = "bifrost"
        port    = "http"
        address = "${bifrost_host}"

        tags = ["http", "llm", "gateway"]

        check {
          type     = "http"
          path     = "/health"
          interval = "30s"
          timeout  = "3s"
        }
      }

      config {
        image        = "docker.io/maximhq/bifrost:v${bifrost_version}"
        network_mode = "host"

        # config.json is the declarative source of truth (GitOps); the
        # SQLite config/log stores live in the container's anonymous
        # /app/data volume and are rebuilt from it on every alloc.
        volumes = [
          "local/config.json:/app/data/config.json",
        ]
      }

      env {
        APP_HOST = "0.0.0.0"
        APP_PORT = "8080"
      }

      vault {}

      # --- provider API keys (resolved by Bifrost via env. references) ---
      template {
        data        = <<EOF
{{- with secret "${ollama_personal_secret}" }}
OLLAMA_KEY_PERSONAL={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${ollama_xebia_secret}" }}
OLLAMA_KEY_XEBIA={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${gemini_secret}" }}
GEMINI_API_KEY={{ .Data.data.GOOGLE_API_KEY }}
{{- end }}
EOF
        destination = "secrets/bifrost.env"
        env         = true
      }

      # --- gateway routing policy: two weighted Ollama Cloud keys
      #     (personal + xebia accounts). Gemini is addressed directly by
      #     consumers via the "gemini/" model prefix ---
      template {
        data = <<EOF
{
  "$schema": "https://www.getbifrost.ai/schema",
  "client": {
    "drop_excess_requests": false,
    "enable_logging": true
  },
  "providers": {
    "ollama": {
      "keys": [
        { "name": "ollama-personal", "value": "env.OLLAMA_KEY_PERSONAL", "models": ["*"], "weight": 0.5, "ollama_key_config": { "url": "https://ollama.com" } },
        { "name": "ollama-xebia", "value": "env.OLLAMA_KEY_XEBIA", "models": ["*"], "weight": 0.5, "ollama_key_config": { "url": "https://ollama.com" } }
      ],
      "network_config": {
        "base_url": "https://ollama.com",
        "default_request_timeout_in_seconds": 120,
        "max_retries": 2
      }
    },
    "gemini": {
      "keys": [
        { "name": "gemini-primary", "value": "env.GEMINI_API_KEY", "models": ["*"], "weight": 1.0 }
      ]
    }
  },
  "config_store": {
    "enabled": true,
    "type": "sqlite",
    "config": { "path": "/app/data/config.db" }
  },
  "logs_store": {
    "enabled": true,
    "type": "sqlite",
    "config": { "path": "/app/data/logs.db" }
  }
}
EOF

        destination = "local/config.json"
      }

      resources {
        cpu    = 300
        memory = 256
      }
    }
  }
}
