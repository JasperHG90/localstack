job "minio" {
  datacenters = ["localstack"]
  type        = "service"

  group "minio" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "orangepi4a"
    }

    volume "minio_data" {
      type            = "host"
      source          = "minio_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    network {
      port "http_api" {
        static = 9000
      }
      port "http_console" {
        static = 9001
      }
    }

    task "minio" {
      driver = "podman"

      vault {}

      template {
        data        = <<-EOH
        MINIO_ROOT_USER="{{ with secret "${minio_secret}" }}{{ .Data.data.access_key }}{{ end }}"
        MINIO_ROOT_PASSWORD="{{ with secret "${minio_secret}" }}{{ .Data.data.secret_key }}{{ end }}"
        EOH
        destination = "secrets/file.env"
        env         = true
      }

      service {
        name = "minio"
        port = "http_console"

        tags = ["http", "s3"]

        check {
          name     = "minio health check (curl)"
          type     = "http"
          path     = "/minio/health/live"
          method   = "GET"
          interval = "10s"
          timeout  = "5s"
        }
      }

      config {
        image   = "docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
        command = "server"
        args    = ["/data", "--console-address", ":9001"]
        ports   = ["http_api", "http_console"]
      }

      volume_mount {
        volume      = "minio_data"
        destination = "/data"
      }

      resources {
        cpu    = 8000
        memory = 3248
      }
    }
  }
}
