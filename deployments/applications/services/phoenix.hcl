job "phoenix" {
  datacenters = ["localstack"]
  type        = "service"

  group "phoenix" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "jetson-orin-nano"
    }

    network {
      port "http" {
        static = 6006
      }
      port "grpc" {
        static = 4317
      }
    }

    task "phoenix" {
      driver = "podman"

      service {
        name    = "phoenix"
        port    = "http"
        address = "${phoenix_host}"

        tags = ["http", "llm", "observability"]

        check {
          type     = "http"
          path     = "/healthz"
          interval = "10s"
          timeout  = "2s"
        }
      }

      service {
        name    = "phoenix-grpc"
        port    = "grpc"
        address = "${phoenix_host}"

        tags = ["grpc", "otlp"]

        check {
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      config {
        image        = "docker.io/arizephoenix/phoenix:latest"
        network_mode = "host"
      }

      vault {}

      template {
        data = <<EOF
          PHOENIX_SQL_DATABASE_URL=postgresql://{{ with secret "${phoenix_secret}" }}{{ .Data.data.username }}:{{ .Data.data.password }}{{ end }}@${postgres_host}:5432/phoenix
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
