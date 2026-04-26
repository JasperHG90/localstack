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
        ]
      }

      volume_mount {
        volume      = "grafana_data"
        destination = "/var/lib/grafana"
      }

      env {
        GF_SECURITY_ADMIN_USER         = "admin"
        GF_SERVER_HTTP_PORT            = "3000"
        GF_USERS_ALLOW_SIGN_UP         = "false"
        GF_ANALYTICS_REPORTING_ENABLED = "false"
        GF_ANALYTICS_CHECK_FOR_UPDATES = "false"
      }

      template {
        data = <<-EOF
        GF_SECURITY_ADMIN_PASSWORD="{{ with secret "${grafana_secret}" }}{{ .Data.data.password }}{{ end }}"
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

      resources {
        cpu    = 500
        memory = 256
      }
    }
  }
}
