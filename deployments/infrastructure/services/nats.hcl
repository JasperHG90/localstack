job "nats" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "nats" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    network {
      port "client" {
        static = 4222
        to     = 4222
      }
      port "monitor" {
        static = 8222
        to     = 8222
      }
      port "metrics" {
        static = 7777
        to     = 7777
      }
    }

    volume "nats_data_volume" {
      type            = "host"
      source          = "nats_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    task "nats" {
      driver = "podman"
      user   = "root"

      service {
        name = "nats"
        port = "client"
        tags = ["nats", "messaging", "jetstream"]

        check {
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      service {
        name         = "nats-monitor"
        port         = "monitor"
        address_mode = "host"
        tags         = ["http", "monitoring"]

        check {
          name         = "nats healthz"
          type         = "http"
          port         = "monitor"
          address_mode = "host"
          path         = "/healthz"
          method       = "GET"
          interval     = "30s"
          timeout      = "3s"
        }
      }

      config {
        image = "docker.io/nats:2.10-alpine"
        args  = ["--config", "/local/nats-server.conf"]
        ports = ["client", "monitor"]
      }

      volume_mount {
        volume      = "nats_data_volume"
        destination = "/data"
      }

      template {
        data = <<EOH
server_name: nats-localstack

listen: 0.0.0.0:4222
http: 0.0.0.0:8222

jetstream {
  store_dir: /data
  max_memory_store: 256MB
  max_file_store: 10GB
}
EOH

        destination = "local/nats-server.conf"
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }

    task "nats-exporter" {
      driver = "podman"

      service {
        name         = "nats-exporter"
        port         = "metrics"
        address_mode = "host"
        tags         = ["http", "monitoring", "prometheus"]

        check {
          name         = "nats-exporter ready"
          type         = "http"
          port         = "metrics"
          address_mode = "host"
          path         = "/metrics"
          method       = "GET"
          interval     = "30s"
          timeout      = "3s"
        }
      }

      config {
        image = "docker.io/natsio/prometheus-nats-exporter:0.17.3"
        args = [
          "-port=7777",
          "-addr=0.0.0.0",
          "-varz",
          "-connz",
          "-routez",
          "-subz",
          "-jsz=all",
          "http://192.168.2.50:8222",
        ]
        ports        = ["metrics"]
        network_mode = "host"
      }

      resources {
        cpu    = 50
        memory = 64
      }
    }
  }
}
