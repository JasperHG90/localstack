job "postgres" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "postgres" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "firebat"
    }

    network {
      port "db" {
        static = 5432
        to     = 5432
      }
      port "exporter" {
        static = 9187
        to     = 9187
      }
    }

    volume "postgres_data_volume" {
      type            = "host"
      source          = "postgres"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    task "postgres" {
      driver = "podman"

      service {
        name = "postgres-db"
        port = "db"

        tags = ["database", "sql"]

        check {
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      env {
        POSTGRES_DB = "localstack"
        PGDATA      = "/var/lib/postgres-nomad-data"
      }

      config {
        image = "docker.io/pgvector/pgvector:pg18-trixie"
        ports = ["db"]
        args = [
          "postgres",
          "-c", "max_connections=200",
          "-c", "shared_buffers=1536MB",
          "-c", "effective_cache_size=4GB",
          "-c", "work_mem=8MB",
          "-c", "maintenance_work_mem=256MB",
          "-c", "wal_buffers=16MB",
        ]
      }

      volume_mount {
        volume      = "postgres_data_volume"
        destination = "/var/lib/postgres-nomad-data"
      }

      vault {}

      template {
        data = <<EOF
          POSTGRES_USER="{{ with secret "${postgres_secret}" }}{{ .Data.data.username }}{{ end }}"
          POSTGRES_PASSWORD="{{ with secret "${postgres_secret}" }}{{ .Data.data.password }}{{ end }}"
        EOF

        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu    = 2000
        memory = 6144
      }
    }

    task "postgres-exporter" {
      driver = "podman"

      lifecycle {
        hook    = "poststart"
        sidecar = true
      }

      vault {}

      service {
        name         = "postgres-exporter"
        port         = "exporter"
        address_mode = "host"
        tags         = ["prometheus", "monitoring"]

        check {
          name         = "postgres-exporter metrics"
          type         = "http"
          port         = "exporter"
          address_mode = "host"
          path         = "/metrics"
          method       = "GET"
          interval     = "30s"
          timeout      = "3s"
        }
      }

      config {
        image        = "docker.io/prometheuscommunity/postgres-exporter:v0.16.0"
        ports        = ["exporter"]
        network_mode = "host"
      }

      template {
        data = <<EOF
          DATA_SOURCE_NAME="postgresql://{{ with secret "${postgres_secret}" }}{{ .Data.data.username }}:{{ .Data.data.password }}{{ end }}@192.168.2.30:5432/localstack?sslmode=disable"
          PG_EXPORTER_WEB_LISTEN_ADDRESS=":9187"
        EOF

        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu    = 200
        memory = 64
      }
    }
  }
}
