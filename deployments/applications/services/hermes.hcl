job "hermes" {
  datacenters = ["localstack"]
  type        = "service"

  group "hermes" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${hermes_hostname}"
    }

    volume "hermes_data_volume" {
      type            = "host"
      source          = "hermes_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    network {
      port "gateway" {
        static = 8642
      }
      port "dashboard" {
        static = 9119
      }
    }

    # ── Prestart: sync IaC config files to the persistent volume ──
    # The main Hermes entrypoint only copies defaults when files are MISSING,
    # so writing our files here ensures they take precedence.
    task "config" {
      driver = "podman"

      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      volume_mount {
        volume      = "hermes_data_volume"
        destination = "/opt/data"
      }

      vault {}

      config {
        image = "docker.io/library/alpine:latest"
        args  = ["/tmp/setup.sh"]

        volumes = [
          "local/hermes.env:/tmp/hermes/hermes.env",
          "local/config.yaml:/tmp/hermes/config.yaml",
          "local/SOUL.md:/tmp/hermes/SOUL.md",
          "local/setup.sh:/tmp/setup.sh",
          "local/skills/devops/cluster-watchdog/SKILL.md:/tmp/hermes/skills/devops/cluster-watchdog/SKILL.md",
          "local/skills/devops/post-mortem/SKILL.md:/tmp/hermes/skills/devops/post-mortem/SKILL.md",
          "local/skills/knowledge/sorting-hat/SKILL.md:/tmp/hermes/skills/knowledge/sorting-hat/SKILL.md",
          "local/skills/knowledge/insight-linker/SKILL.md:/tmp/hermes/skills/knowledge/insight-linker/SKILL.md",
          "local/skills/finance/trader-advisor/SKILL.md:/tmp/hermes/skills/finance/trader-advisor/SKILL.md",
          "local/skills/finance/market-analyst/SKILL.md:/tmp/hermes/skills/finance/market-analyst/SKILL.md",
          "local/skills/finance/trend-scout/SKILL.md:/tmp/hermes/skills/finance/trend-scout/SKILL.md",
          "local/skills/productivity/blog-scraper/SKILL.md:/tmp/hermes/skills/productivity/blog-scraper/SKILL.md",
          "local/skills/productivity/medium-reader/SKILL.md:/tmp/hermes/skills/productivity/medium-reader/SKILL.md",
          "local/skills/productivity/researcher/SKILL.md:/tmp/hermes/skills/productivity/researcher/SKILL.md",
          "local/skills/productivity/collector/SKILL.md:/tmp/hermes/skills/productivity/collector/SKILL.md",
          "local/skills/devops/hermes-watcher/SKILL.md:/tmp/hermes/skills/devops/hermes-watcher/SKILL.md",
        ]
      }

      template {
        data = <<EOF
#!/bin/sh
set -e

mkdir -p /opt/data/sessions /opt/data/memories /opt/data/cron \
         /opt/data/hooks /opt/data/logs /opt/data/skills

chmod -R 777 /opt/data

# Strip TELEGRAM_BOT_TOKEN if it contains PLACEHOLDER (invalid token crashes gateway)
# Download Memex Hermes plugin + dependency
mkdir -p /opt/data/plugins
wget -q -O /opt/data/plugins/memex_common-0.1.12-py3-none-any.whl \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.12/memex_common-0.1.12-py3-none-any.whl" \
  2>/dev/null || echo "WARN: failed to download memex-common"
wget -q -O /opt/data/plugins/memex_hermes_plugin-0.1.12-py3-none-any.whl \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.12/memex_hermes_plugin-0.1.12-py3-none-any.whl" \
  2>/dev/null || echo "WARN: failed to download memex plugin"

cp /tmp/hermes/hermes.env /opt/data/.env
cp /tmp/hermes/config.yaml /opt/data/config.yaml
cp /tmp/hermes/SOUL.md /opt/data/SOUL.md

if [ -d /tmp/hermes/skills ]; then
  cp -r /tmp/hermes/skills/* /opt/data/skills/ 2>/dev/null || true
fi

echo "hermes: config sync complete"
EOF

        destination = "local/setup.sh"
        perms       = "0755"
      }

      # --- .env (secrets from Vault) ---
      template {
        data = <<EOF
{{- with secret "${openrouter_secret}" }}
OPENROUTER_API_KEY={{ .Data.data.api_key }}
{{- end }}
{{- with secret "${ollama_secret}" }}
OLLAMA_API_KEY={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${telegram_secret}" }}
TELEGRAM_BOT_TOKEN={{ .Data.data.bot_token }}
{{- end }}
TELEGRAM_ALLOWED_USERS=${telegram_allowed_users}
{{- with secret "${email_secret}" }}
EMAIL_ADDRESS=<REDACTED_EMAIL>
EMAIL_PASSWORD={{ .Data.data.EMAIL_PASSWORD }}
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_SMTP_HOST=smtp.gmail.com
{{- end }}
{{- with secret "${github_secret}" }}
GITHUB_PERSONAL_ACCESS_TOKEN={{ .Data.data.pat }}
{{- end }}
{{- with secret "${nomad_secret}" }}
NOMAD_TOKEN={{ .Data.data.token }}
{{- end }}
{{- with secret "${memex_auth_secret}" }}
MEMEX_API_KEY={{ .Data.data.admin_key }}
{{- end }}
MEMEX_SERVER_URL=http://${memex_host}:8000
NOMAD_ADDR=http://192.168.2.30:4646
CONSUL_ADDR=http://192.168.2.30:8500
HERMES_YOLO_MODE=true
HERMES_HOME=/opt/data
OLLAMA_BASE_URL=https://ollama.com/v1
EOF

        destination = "local/hermes.env"
      }

      # --- config.yaml ---
      template {
        data = <<EOF
model:
  provider: "ollama-cloud"
  name: "glm-5.1"

fallback_model:
  provider: "openrouter"
  model: "google/gemini-3-flash-preview"

agent:
  max_turns: 90
  reasoning_effort: "medium"

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: "memex"

terminal:
  backend: "local"
  cwd: "/opt/data"
  timeout: 180

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20

approvals:
  mode: "off"

auxiliary:
  compression:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite-preview"
  session_search:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite-preview"
  flush_memories:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite-preview"

platform_toolsets:
  email:
    - terminal
    - web
    - browser
    - memory
    - skills
    - files
  telegram:
    - terminal
    - web
    - browser
    - memory
    - skills
    - files

mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "$${GITHUB_PERSONAL_ACCESS_TOKEN}"
    enabled: true

telegram:
  require_mention: false
EOF

        destination = "local/config.yaml"
      }

      template {
        data        = <<-EOT
${soul_md}
EOT
        destination = "local/SOUL.md"
      }

      template {
        data        = <<-EOT
${skill_cluster_watchdog}
EOT
        destination = "local/skills/devops/cluster-watchdog/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_post_mortem}
EOT
        destination = "local/skills/devops/post-mortem/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_sorting_hat}
EOT
        destination = "local/skills/knowledge/sorting-hat/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_insight_linker}
EOT
        destination = "local/skills/knowledge/insight-linker/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_trader_advisor}
EOT
        destination = "local/skills/finance/trader-advisor/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_market_analyst}
EOT
        destination = "local/skills/finance/market-analyst/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_trend_scout}
EOT
        destination = "local/skills/finance/trend-scout/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_blog_scraper}
EOT
        destination = "local/skills/productivity/blog-scraper/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_medium_reader}
EOT
        destination = "local/skills/productivity/medium-reader/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_researcher}
EOT
        destination = "local/skills/productivity/researcher/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_collector}
EOT
        destination = "local/skills/productivity/collector/SKILL.md"
      }

      template {
        data        = <<-EOT
${skill_hermes_watcher}
EOT
        destination = "local/skills/devops/hermes-watcher/SKILL.md"
      }

      resources {
        cpu    = 200
        memory = 64
      }
    }

    # ── Gateway: main Hermes agent process ──
    # Uses the ORIGINAL entrypoint which creates dirs, syncs bundled skills,
    # then runs `hermes gateway run`.
    task "hermes" {
      driver = "podman"

      volume_mount {
        volume      = "hermes_data_volume"
        destination = "/opt/data"
      }

      service {
        name    = "hermes"
        port    = "gateway"
        address = "${hermes_host}"

        tags = ["http", "hermes", "agent"]

        check {
          type     = "tcp"
          port     = "gateway"
          interval = "15s"
          timeout  = "5s"
        }
      }

      vault {}

      template {
        data = <<EOF
{{- with secret "${openrouter_secret}" }}
OPENROUTER_API_KEY={{ .Data.data.api_key }}
{{- end }}
{{- with secret "${ollama_secret}" }}
OLLAMA_API_KEY={{ .Data.data.API_KEY }}
{{- end }}
{{- with secret "${telegram_secret}" }}
TELEGRAM_BOT_TOKEN={{ .Data.data.bot_token }}
{{- end }}
{{- with secret "${email_secret}" }}
EMAIL_PASSWORD={{ .Data.data.EMAIL_PASSWORD }}
{{- end }}
{{- with secret "${github_secret}" }}
GITHUB_PERSONAL_ACCESS_TOKEN={{ .Data.data.pat }}
GH_TOKEN={{ .Data.data.pat }}
{{- end }}
{{- with secret "${nomad_secret}" }}
NOMAD_TOKEN={{ .Data.data.token }}
{{- end }}
{{- with secret "${memex_auth_secret}" }}
MEMEX_API_KEY={{ .Data.data.admin_key }}
{{- end }}
EOF

        destination = "secrets/file.env"
        env         = true
      }

      env {
        HERMES_HOME            = "/opt/data"
        HERMES_YOLO_MODE       = "true"
        MEMEX_SERVER_URL       = "http://${memex_host}:8000"
        NOMAD_ADDR             = "http://192.168.2.30:4646"
        CONSUL_ADDR            = "http://192.168.2.30:8500"
        TELEGRAM_ALLOWED_USERS = "${telegram_allowed_users}"
        EMAIL_ADDRESS          = "<REDACTED_EMAIL>"
        EMAIL_IMAP_HOST        = "imap.gmail.com"
        EMAIL_SMTP_HOST        = "smtp.gmail.com"
        OLLAMA_BASE_URL        = "https://ollama.com/v1"
        API_SERVER_ENABLED     = "true"
        API_SERVER_HOST        = "0.0.0.0"
        API_SERVER_KEY         = "${api_server_key}"
        GATEWAY_HEALTH_TIMEOUT = "5"
      }

      config {
        image        = "ghcr.io/jasperhg90/hermes:${hermes_version}"
        args         = ["gateway", "run"]
        network_mode = "host"
        shm_size     = "1g"
      }

      resources {
        cpu        = 2000
        memory     = 2048
        memory_max = 2560
      }
    }

    # ── Dashboard: web UI for sessions, config, cron, analytics ──
    # Separate process sharing the same data volume.
    task "dashboard" {
      driver = "podman"

      lifecycle {
        hook    = "poststart"
        sidecar = true
      }

      volume_mount {
        volume      = "hermes_data_volume"
        destination = "/opt/data"
      }

      service {
        name    = "hermes-dashboard"
        port    = "dashboard"
        address = "${hermes_host}"

        tags = ["http", "hermes", "dashboard"]

        check {
          type     = "http"
          path     = "/api/status"
          port     = "dashboard"
          interval = "15s"
          timeout  = "5s"
        }
      }

      env {
        HERMES_HOME        = "/opt/data"
        GATEWAY_HEALTH_URL = "http://127.0.0.1:8642"
      }

      config {
        image        = "ghcr.io/jasperhg90/hermes:${hermes_version}"
        args         = ["dashboard", "--host", "0.0.0.0", "--port", "9119", "--no-open", "--insecure"]
        network_mode = "host"
      }

      resources {
        cpu    = 500
        memory = 256
      }
    }
  }
}
