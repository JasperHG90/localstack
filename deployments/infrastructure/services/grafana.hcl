job "grafana" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "grafana" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    network {
      port "http" {
        static = 3000
      }
    }

    volume "grafana_data" {
      type            = "host"
      source          = "grafana_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    task "grafana" {
      driver = "podman"
      user   = "root"

      vault {}

      service {
        name = "grafana"
        port = "http"
        tags = ["http", "monitoring"]

        check {
          name     = "grafana health"
          type     = "http"
          port     = "http"
          path     = "/api/health"
          method   = "GET"
          interval = "10s"
          timeout  = "3s"
        }
      }

      config {
        image        = "docker.io/grafana/grafana:11.5.2"
        ports        = ["http"]
        network_mode = "host"
        volumes = [
          "local/provisioning/datasources/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml:ro",
          "local/provisioning/dashboards/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml:ro",
          "local/dashboards:/etc/grafana/dashboards:ro",
          "local/provisioning/alerting/contactpoints.yaml:/etc/grafana/provisioning/alerting/contactpoints.yaml:ro",
          "local/provisioning/alerting/policies.yaml:/etc/grafana/provisioning/alerting/policies.yaml:ro",
          "local/provisioning/alerting/templates.yaml:/etc/grafana/provisioning/alerting/templates.yaml:ro",
          "local/provisioning/alerting/rules.yaml:/etc/grafana/provisioning/alerting/rules.yaml:ro",
        ]
      }

      volume_mount {
        volume      = "grafana_data"
        destination = "/var/lib/grafana"
      }

      ### GF_SERVER_ROOT_URL is the single input Grafana derives its OIDC
      ### redirect URI from, so it must be the edge hostname registered in
      ### `local.grafana_redirect_url` (oidc.tf), not a node address. A
      ### mismatch fails at the provider with an opaque error, not at Grafana.
      env {
        GF_SECURITY_ADMIN_USER         = "admin"
        GF_SERVER_HTTP_PORT            = "3000"
        GF_SERVER_ROOT_URL             = "https://grafana.lab.orangecluster.nl"
        GF_USERS_ALLOW_SIGN_UP         = "false"
        GF_ANALYTICS_REPORTING_ENABLED = "false"
        GF_ANALYTICS_CHECK_FOR_UPDATES = "false"
        GF_UNIFIED_ALERTING_ENABLED    = "true"

        ### Vault SSO through Grafana's own generic OAuth client. No proxy.
        ###
        ### Four of these look optional and are not:
        ###
        ###   AUTH_URL/TOKEN_URL/API_URL are spelled out because 11.5.2's generic
        ###   OAuth client does NO OIDC discovery — it never reads the
        ###   well-known document, so an issuer URL alone configures nothing.
        ###   AUTH_URL is a Vault *UI* path; that is what discovery advertises.
        ###
        ###   SCOPES must be set and must contain `openid`. Grafana's default is
        ###   `user:email`, and Vault's authorize handler hard-rejects a request
        ###   whose scope omits `openid`, so the default cannot reach the token
        ###   endpoint at all. `email` is the claim Grafana refuses to log a user
        ###   in without; Vault drops an unrequested scope silently.
        ###
        ###   ROLE_ATTRIBUTE_PATH is a JMESPath raw-string literal, quotes
        ###   included, and it resolves against any input. Without it Grafana
        ###   falls back to auto_assign_org_role, which ships as Viewer — every
        ###   SSO user lands read-only while nothing errors.
        ###
        ### GF_USERS_ALLOW_SIGN_UP = "false" above does NOT block these logins:
        ### the OAuth path consults the per-connector allow_sign_up, which
        ### defaults to true.
        GF_AUTH_GENERIC_OAUTH_ENABLED              = "true"
        GF_AUTH_GENERIC_OAUTH_NAME                 = "Vault"
        GF_AUTH_GENERIC_OAUTH_AUTH_URL             = "https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize"
        GF_AUTH_GENERIC_OAUTH_TOKEN_URL            = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/token"
        GF_AUTH_GENERIC_OAUTH_API_URL              = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/userinfo"
        GF_AUTH_GENERIC_OAUTH_SCOPES               = "openid email"
        GF_AUTH_GENERIC_OAUTH_EMAIL_ATTRIBUTE_PATH = "email"
        GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH  = "'Editor'"
      }

      template {
        data = <<-EOF
        GF_SECURITY_ADMIN_PASSWORD="{{ with secret "${grafana_secret}" }}{{ .Data.data.password }}{{ end }}"
        GF_AUTH_GENERIC_OAUTH_CLIENT_ID="{{ with secret "${grafana_oidc_secret}" }}{{ .Data.data.client_id }}{{ end }}"
        GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET="{{ with secret "${grafana_oidc_secret}" }}{{ .Data.data.client_secret }}{{ end }}"
        EOF

        destination = "secrets/file.env"
        env         = true
      }

      template {
        data = <<-EOF
        apiVersion: 1
        datasources:
          - name: Prometheus
            uid: prometheus
            type: prometheus
            access: proxy
            url: http://192.168.2.47:9090
            isDefault: true
            editable: false
          - name: Loki
            uid: loki
            type: loki
            access: proxy
            url: http://192.168.2.47:3100
            editable: false
            jsonData:
              # Turns a trace_id on a log line into a link into Tempo. Loki
              # writes trace_id as structured metadata for logs it ingests over
              # OTLP, hence matcherType `label` rather than a regex over the
              # message body. Logs with no trace_id are unaffected.
              derivedFields:
                - name: TraceID
                  matcherType: label
                  matcherRegex: trace_id
                  datasourceUid: tempo
                  url: "$${__value.raw}"
          - name: Tempo
            uid: tempo
            type: tempo
            access: proxy
            url: http://192.168.2.47:3200
            editable: false
            jsonData:
              # The other half of the round trip: from a span, jump to the logs
              # written while it was open.
              tracesToLogsV2:
                datasourceUid: loki
                spanStartTimeShift: "-5m"
                spanEndTimeShift: "5m"
                filterByTraceID: true
        EOF

        destination = "local/provisioning/datasources/datasources.yml"
      }

      template {
        data = <<-EOF
        apiVersion: 1
        providers:
          - name: localstack
            orgId: 1
            folder: ""
            type: file
            disableDeletion: true
            updateIntervalSeconds: 30
            allowUiUpdates: false
            options:
              path: /etc/grafana/dashboards
              foldersFromFilesStructure: false
        EOF

        destination = "local/provisioning/dashboards/dashboards.yml"
      }

      template {
        # Custom delimiters so consul-template doesn't try to interpret
        # Grafana's {{ }} legend syntax inside the JSON.
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${cluster_overview_dashboard}
        EOF

        destination = "local/dashboards/cluster-overview.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${logs_dashboard}
        EOF

        destination = "local/dashboards/logs.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${services_dashboard}
        EOF

        destination = "local/dashboards/services.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${node_dashboard}
        EOF

        destination = "local/dashboards/node-detail.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${nomad_dashboard}
        EOF

        destination = "local/dashboards/nomad.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${postgres_dashboard}
        EOF

        destination = "local/dashboards/postgres.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${minio_dashboard}
        EOF

        destination = "local/dashboards/minio.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${ingress_dashboard}
        EOF

        destination = "local/dashboards/ingress.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${nats_dashboard}
        EOF

        destination = "local/dashboards/nats.json"
      }

      template {
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
        ${bifrost_dashboard}
        EOF

        destination = "local/dashboards/bifrost.json"
      }

      # ---- Unified alerting: contact point (Telegram) ----
      template {
        data = <<-EOF
        apiVersion: 1
        contactPoints:
          - orgId: 1
            name: telegram-default
            receivers:
              - uid: telegram-default
                type: telegram
                disableResolveMessage: false
                settings:
                  bottoken: '{{ with secret "${telegram_secret}" }}{{ .Data.data.bot_token }}{{ end }}'
                  chatid: "${telegram_alert_chat_id}"
                  parse_mode: HTML
                  message: |
                    {{`{{ template "telegram.message" . }}`}}
        EOF

        destination = "local/provisioning/alerting/contactpoints.yaml"
        change_mode = "restart"
      }

      # ---- Unified alerting: notification policy ----
      template {
        data = <<-EOF
        apiVersion: 1
        policies:
          - orgId: 1
            receiver: telegram-default
            group_by: [alertname, severity, instance]
            group_wait: 30s
            group_interval: 5m
            repeat_interval: 4h
            routes:
              - receiver: telegram-default
                matchers:
                  - severity = critical
                group_wait: 10s
                group_interval: 2m
                repeat_interval: 30m
              - receiver: telegram-default
                matchers:
                  - severity = warning
                group_wait: 1m
                group_interval: 10m
                repeat_interval: 4h
        EOF

        destination = "local/provisioning/alerting/policies.yaml"
        change_mode = "restart"
      }

      # ---- Unified alerting: message template ----
      template {
        data = <<-EOF
        apiVersion: 1
        templates:
          - orgId: 1
            name: telegram.message
            template: |
              {{`{{ define "telegram.message" }}`}}
              {{`{{ range .Alerts }}`}}
              {{`{{ if eq .Status "firing" }}`}}<b>{{`{{ if eq .Labels.severity "critical" }}`}}CRITICAL 🔥{{`{{ else }}`}}WARNING ⚠️{{`{{ end }}`}}</b>
              {{`{{ else }}`}}<b>RESOLVED ✅</b>
              {{`{{ end }}`}}
              <b>Alert:</b> {{`{{ .Labels.alertname }}`}}
              <b>Instance:</b> <code>{{`{{ .Labels.instance }}`}}</code>
              <b>Component:</b> {{`{{ .Labels.component }}`}}
              <b>Summary:</b> {{`{{ .Annotations.summary }}`}}
              <b>Detail:</b> {{`{{ .Annotations.description }}`}}
              <a href="${grafana_external_url}/alerting/list">Open Grafana</a>
              {{`{{ end }}`}}
              {{`{{ end }}`}}
        EOF

        destination = "local/provisioning/alerting/templates.yaml"
        change_mode = "restart"
      }

      # ---- Unified alerting: rules ----
      template {
        # Custom delimiters so consul-template doesn't try to interpret
        # Grafana's {{ $labels.* }} templating syntax in the rule annotations.
        # Placeholder is at column 0 (not indented) so the substituted YAML
        # keeps its native indentation across the first line.
        left_delimiter  = "<<<<"
        right_delimiter = ">>>>"
        data            = <<-EOF
${alert_rules}
        EOF

        destination = "local/provisioning/alerting/rules.yaml"
        change_mode = "restart"
      }

      resources {
        cpu    = 500
        memory = 256
      }
    }
  }
}
