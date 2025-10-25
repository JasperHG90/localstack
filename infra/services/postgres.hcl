# Run job using `nomad job run /home/vscode/workspace/services/postgres/postgresql.hcl`
job "postgres" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "postgres" {
    network {
      port "db" {
        static = 5432
        to     = 5432
      }
    }

    # Defined in /etc/nomad.d/nomad.hcl
    volume "postgres_data_volume" {
      type   = "host"
      source = "postgres-host-data"
    }

    task "postgres" {
      driver = "podman"

      service {
        name = "postgres-db"
        port = "db"

        tags = ["database", "sql", "urlprefix-localstack.local/postgres/"]

        check {
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      env {
        POSTGRES_DB = "localstack"
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
        cpu    = 1000
        memory = 2048
      }
    }
  }
}
