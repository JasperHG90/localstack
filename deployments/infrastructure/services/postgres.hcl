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
        image = "docker.io/library/postgres:18"
        ports = ["db"]
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
        memory = 4096
      }
    }
  }
}
