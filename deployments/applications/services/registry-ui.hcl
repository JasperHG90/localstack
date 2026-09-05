job "registry-ui" {
  datacenters = ["localstack"]
  type        = "service"

  group "registry-ui" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    network {
      port "http" {
        static = 8002
      }
      port "backend" {
        static = 8003
      }
    }

    ### Holds the registry view's SQLite store. A cards row is keyed by a
    ### content digest, so it is never invalidated: this volume is what makes
    ### a restart cost no re-walk of the registry.
    volume "registry_ui_data" {
      type      = "host"
      source    = "registry_ui_data"
      read_only = false
    }

    task "frontend" {
      driver = "podman"

      service {
        name = "registry-ui-frontend"
        port = "http"

        check {
          type     = "http"
          path     = "/"
          interval = "30s"
          timeout  = "5s"
        }
      }

      config {
        image        = "ghcr.io/jasperhg90/registry-ui-frontend:${registry_ui_frontend_version}"
        network_mode = "host"
      }

      resources {
        cpu    = 50
        memory = 32
      }
    }

    task "backend" {
      driver = "podman"

      service {
        name = "registry-ui-backend"
        port = "backend"

        check {
          type     = "http"
          path     = "/api/registry"
          interval = "60s"
          timeout  = "30s"
        }
      }

      config {
        image        = "ghcr.io/jasperhg90/registry-ui-backend:${registry_ui_backend_version}"
        network_mode = "host"
      }

      volume_mount {
        volume      = "registry_ui_data"
        destination = "/var/lib/registry-ui"
      }

      env {
        REGISTRY_ADDR            = "${registry_addr}"
        REGISTRY_CREDENTIAL_FILE = "/secrets/registry.json"
        REGISTRY_DB_PATH         = "/var/lib/registry-ui/registry.db"
        PORT                     = "8003"
      }

      vault {}

      ### This job's OWN copy of the registry credential. The nomad-workloads
      ### role grants a job read only under secret/data/default/<job_id>/*,
      ### so reading the registry's own default/registry/auth would 403.
      ### Read-only use: this service lists repositories and reads manifests
      ### and small blobs, and never pushes.
      template {
        data        = <<-EOF
        {{- with secret "${registry_auth_secret}" }}
        {"username":"{{ .Data.data.username }}","password":"{{ .Data.data.password }}"}
        {{- end }}
        EOF
        destination = "secrets/registry.json"
        change_mode = "restart"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
