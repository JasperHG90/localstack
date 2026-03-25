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
provider = "minimax"
model = "minimax/MiniMax-M2.5"
api_key_env = "MINIMAX_API_KEY"

[channels.telegram]
bot_token_env = "TELEGRAM_BOT_TOKEN"
allowed_users = [${join(", ", telegram_allowed_users)}]

EOF

        destination = "local/config.toml"
      }

      config {
        volumes = [
          "local/config.toml:/data/config.toml",
        ]
        image        = "ghcr.io/jasperhg90/openfang:${openfang_version}"
        force_pull   = true
        network_mode = "host"
      }

      resources {
        cpu    = 6000
        memory = 2800
      }
    }
  }
}
