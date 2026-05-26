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

      user = "0"

      config {
        image      = "ghcr.io/jasperhg90/hermes:${hermes_version}"
        entrypoint = ["/bin/sh"]
        args       = ["/tmp/setup.sh"]

        volumes = [
          "local/hermes.env:/tmp/hermes/hermes.env",
          "local/config.yaml:/tmp/hermes/config.yaml",
          "local/SOUL.md:/tmp/hermes/SOUL.md",
          "local/setup.sh:/tmp/setup.sh",
          "local/skills:/tmp/hermes/skills:ro",
        ]
      }

      template {
        data = <<EOF
#!/bin/sh
set -e

mkdir -p /opt/data/sessions /opt/data/memories /opt/data/cron \
         /opt/data/hooks /opt/data/logs /opt/data/skills /opt/data/plugins

# Ensure ownership so subsequent hermes user processes can write
HERMES_UID=$(id -u hermes 2>/dev/null || echo 1000)
HERMES_GID=$(id -g hermes 2>/dev/null || echo 1000)
chown -R $HERMES_UID:$HERMES_GID /opt/data 2>/dev/null || true

cp /tmp/hermes/hermes.env /opt/data/.env
cp /tmp/hermes/config.yaml /opt/data/config.yaml
cp /tmp/hermes/SOUL.md /opt/data/SOUL.md

# IaC-managed read-only skill library. Refreshed from scratch every deploy
# so removed skills are pruned. Wired into config.yaml via
# skills.external_dirs; the agent cannot modify files here (enforced by
# Hermes: skill_manage refuses writes outside HERMES_HOME/skills).
# Writable agent skills live in /opt/data/skills/ and are never touched here.
if [ -d /tmp/hermes/skills ]; then
  rm -rf /opt/data/skills-library
  mkdir -p /opt/data/skills-library
  cp -r /tmp/hermes/skills/* /opt/data/skills-library/ 2>/dev/null || true
fi

# External read-only library: JasperHG90/skills (public, refresh per deploy).
# Tarball avoids needing git in the image. Failure here is non-fatal: the
# agent loses access to those skills but the deploy continues.
EXT_JG_REF="${external_skills_jasperhg90_ref}"
rm -rf /opt/data/skills-library-jasperhg90
mkdir -p /opt/data/skills-library-jasperhg90
if curl -fsSL "https://github.com/JasperHG90/skills/archive/$EXT_JG_REF.tar.gz" \
   | tar xz -C /opt/data/skills-library-jasperhg90 --strip-components=1 2>/dev/null; then
  echo "hermes: external skills jasperhg90@$EXT_JG_REF synced"
else
  echo "hermes: WARN failed to fetch external skills jasperhg90@$EXT_JG_REF (continuing)"
fi

# Copy Memex plugin from staged location in custom image
if [ -d /opt/hermes/memex-plugin ]; then
  mkdir -p /opt/data/plugins/memex
  cp -r /opt/hermes/memex-plugin/* /opt/data/plugins/memex/
  echo "hermes: memex plugin synced"
fi

# Final ownership pass — everything we just wrote
chown -R $HERMES_UID:$HERMES_GID /opt/data 2>/dev/null || true

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
TELEGRAM_HOME_CHANNEL=${telegram_allowed_users}
{{- with secret "${email_secret}" }}
EMAIL_ADDRESS=${hermes_email_address}
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
MEMEX_VAULT=hermes
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
  default: "gemma4:31b-cloud"
  context_length: 128000

fallback_model:
  provider: "openrouter"
  model: "google/gemini-3-flash-preview"

agent:
  max_turns: 90
  reasoning_effort: "medium"

plugins:
  enabled:
    - memex
  disabled: []

skills:
  external_dirs:
    - /opt/data/skills-library
    - /opt/data/skills-library-jasperhg90/skills

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
  env_passthrough:
    - MEMEX_API_KEY
    - MEMEX_SERVER_URL
    - MEMEX_VAULT
    - NOMAD_TOKEN
    - NOMAD_ADDR
    - CONSUL_ADDR
    - GH_TOKEN
    - GITHUB_PERSONAL_ACCESS_TOKEN

code_execution:
  env_passthrough:
    - MEMEX_API_KEY
    - MEMEX_SERVER_URL
    - MEMEX_VAULT
    - NOMAD_TOKEN
    - NOMAD_ADDR
    - CONSUL_ADDR
    - GH_TOKEN
    - GITHUB_PERSONAL_ACCESS_TOKEN

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20

approvals:
  mode: "off"

dashboard:
  theme: "mono"

auxiliary:
  compression:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite"
  session_search:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite"
  flush_memories:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite"
  title_generation:
    provider: "openrouter"
    model: "google/gemini-3.1-flash-lite"

platform_toolsets:
  email:
    - terminal
    - web
    - browser
    - memory
    - memex
    - skills
    - files
    - cronjob
  telegram:
    - terminal
    - web
    - browser
    - memory
    - memex
    - skills
    - files
    - cronjob

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

%{ for path, body in skills ~}
      template {
        data        = <<-EOT
${body}
EOT
        destination = "local/skills/${path}/SKILL.md"
      }
%{ endfor ~}

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
{{- with secret "${api_server_secret}" }}
API_SERVER_KEY={{ .Data.data.key }}
{{- end }}
EOF

        destination = "secrets/file.env"
        env         = true
      }

      # Prune bundled skills overridden by IaC skills-library, then run gateway.
      # The base image's entrypoint runs skills_sync.py which copies bundled
      # skills into /opt/data/skills/. Several of those collide with skills we
      # ship via skills-library, and Hermes refuses to load ambiguous names —
      # silently breaking cron jobs like hermes-watcher and cluster-watchdog.
      # We invoke the prune AFTER entrypoint setup (entrypoint execs $@ if $1
      # is on PATH) so the venv is active and skills_sync.py has already run.
      template {
        data        = <<-EOT
          #!/bin/sh
          set -e
          if [ -d /opt/data/skills-library ]; then
            find /opt/data/skills-library -name SKILL.md \
              | sed -e 's|^/opt/data/skills-library/||' -e 's|/SKILL.md$||' \
              | while IFS= read -r rel; do
                  if [ -e "/opt/data/skills/$rel" ]; then
                    echo "prune: /opt/data/skills/$rel (overridden by IaC)"
                    rm -rf "/opt/data/skills/$rel"
                  fi
                done
          fi
          exec hermes gateway run
        EOT
        destination = "local/start-hermes.sh"
        perms       = "0755"
      }

      env {
        HERMES_HOME            = "/opt/data"
        HERMES_YOLO_MODE       = "true"
        MEMEX_SERVER_URL       = "http://${memex_host}:8000"
        MEMEX_VAULT            = "hermes"
        NOMAD_ADDR             = "http://192.168.2.30:4646"
        CONSUL_ADDR            = "http://192.168.2.30:8500"
        TELEGRAM_ALLOWED_USERS = "${telegram_allowed_users}"
        TELEGRAM_HOME_CHANNEL  = "${telegram_allowed_users}"
        EMAIL_ADDRESS          = "${hermes_email_address}"
        EMAIL_IMAP_HOST        = "imap.gmail.com"
        EMAIL_SMTP_HOST        = "smtp.gmail.com"
        DIGEST_EMAIL           = "${hermes_digest_email}"
        OLLAMA_BASE_URL        = "https://ollama.com/v1"
        API_SERVER_ENABLED     = "true"
        API_SERVER_HOST        = "0.0.0.0"
        GATEWAY_HEALTH_TIMEOUT = "5"
      }

      config {
        image        = "ghcr.io/jasperhg90/hermes:${hermes_version}"
        args         = ["sh", "/local/start-hermes.sh"]
        network_mode = "host"
        shm_size     = "1g"

        volumes = [
          "local/start-hermes.sh:/local/start-hermes.sh:ro",
        ]
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
