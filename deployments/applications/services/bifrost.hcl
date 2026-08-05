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

        # governance.auth_config is enabled, so /metrics requires basic_auth.
        # This service is NOT tagged "prometheus": the shared consul_services
        # job cannot carry per-target basic_auth, so prometheus.hcl scrapes
        # bifrost via a dedicated basic_auth job instead.
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

        # config.json is the declarative source of truth (GitOps). The
        # config_store is Postgres (persistent) so governance virtual keys
        # survive restarts and the admin UI can manage them; the logs_store
        # stays SQLite on the anonymous /app/data volume, rebuilt per alloc.
        volumes = [
          "local/config.json:/app/data/config.json",
        ]
      }

      env {
        APP_HOST = "0.0.0.0"
        APP_PORT = "8080"
      }

      vault {}

      # --- provider API keys + admin creds (resolved by Bifrost via env. references) ---
      template {
        data        = <<EOF
{{- with secret "${bifrost_credentials_secret}" }}
BIFROST_ADMIN_USERNAME={{ .Data.data.username }}
BIFROST_ADMIN_PASSWORD={{ .Data.data.password }}
{{- end }}
{{- with secret "${ollama_personal_secret}" }}
OLLAMA_KEY_PERSONAL={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${ollama_xebia_secret}" }}
OLLAMA_KEY_XEBIA={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${ollama_proton_secret}" }}
OLLAMA_KEY_PROTON={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${ollama_rituals_secret}" }}
OLLAMA_KEY_RITUALS={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${gemini_secret}" }}
GEMINI_API_KEY={{ .Data.data.GOOGLE_API_KEY }}
{{- end }}
PG_HOST=${bifrost_postgres_host}
{{- with secret "${bifrost_db_secret}" }}
PG_USER={{ .Data.data.username }}
PG_PASSWORD={{ .Data.data.password }}
{{- end }}
EOF
        destination = "secrets/bifrost.env"
        env         = true
      }

      # --- gateway routing policy: four weighted Ollama Cloud keys
      #     (personal + xebia + proton + rituals accounts). Gemini is addressed directly
      #     by consumers via the "gemini/" model prefix ---
      template {
        data = <<EOF
{
  "$schema": "https://www.getbifrost.ai/schema",
  "client": {
    "drop_excess_requests": false,
    "enable_logging": true,
    "enforce_auth_on_inference": true
  },
  "governance": {
    "auth_config": {
      "is_enabled": true,
      "admin_username": "env.BIFROST_ADMIN_USERNAME",
      "admin_password": "env.BIFROST_ADMIN_PASSWORD"
    }
  },
  "providers": {
    "ollama": {
      "keys": [
        { "name": "ollama-personal", "value": "env.OLLAMA_KEY_PERSONAL", "models": ["*"], "weight": 0.5, "ollama_key_config": { "url": "https://ollama.com" } },
        { "name": "ollama-xebia", "value": "env.OLLAMA_KEY_XEBIA", "models": ["*"], "weight": 0.5, "ollama_key_config": { "url": "https://ollama.com" } },
        { "name": "ollama-proton", "value": "env.OLLAMA_KEY_PROTON", "models": ["*"], "weight": 0.5, "ollama_key_config": { "url": "https://ollama.com" } },
        { "name": "ollama-rituals", "value": "env.OLLAMA_KEY_RITUALS", "models": ["*"], "weight": 0.5, "ollama_key_config": { "url": "https://ollama.com" } }
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
    "type": "postgres",
    "config": {
      "host": "env.PG_HOST",
      "port": "5432",
      "user": "env.PG_USER",
      "password": "env.PG_PASSWORD",
      "db_name": "bifrost",
      "ssl_mode": "disable"
    }
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
        cpu    = 600
        memory = 512
      }
    }
  }
}
