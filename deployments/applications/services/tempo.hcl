job "tempo" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "tempo" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    network {
      port "http" {
        static = 3200
      }
      # Tempo's gRPC server defaults to 9095, which Loki already holds on this
      # node under network_mode = host. Moved to 9096; nothing dials it (the
      # single binary talks to itself), it just needs to bind somewhere free.
      port "grpc" {
        static = 9096
      }
      port "otlp_grpc" {
        static = 4317
      }
      port "otlp_http" {
        static = 4318
      }
    }

    volume "tempo_data" {
      type            = "host"
      source          = "tempo_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    task "tempo" {
      driver = "podman"
      user   = "root"

      vault {}

      service {
        name = "tempo"
        port = "http"
        tags = ["http", "monitoring"]

        check {
          name     = "tempo ready"
          type     = "http"
          port     = "http"
          path     = "/ready"
          method   = "GET"
          interval = "15s"
          timeout  = "3s"
        }
      }

      config {
        image = "docker.io/grafana/tempo:2.10.8"
        args = [
          "-config.file=/local/tempo-config.yaml",
          "-config.expand-env=true",
        ]
        ports        = ["http", "grpc", "otlp_grpc", "otlp_http"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "tempo_data"
        destination = "/var/tempo"
      }

      template {
        data = <<-EOF
        {{- with secret "${tempo_minio_secret}" }}
        MINIO_ACCESS_KEY="{{ .Data.data.access_key }}"
        MINIO_SECRET_KEY="{{ .Data.data.secret_key }}"
        {{- end }}
        EOF

        destination = "secrets/minio.env"
        env         = true
      }

      template {
        data = <<-EOF
        server:
          http_listen_port: 3200
          grpc_listen_port: 9096
          log_level: info

        # Receivers bind to localhost unless given an address, which would
        # make Tempo unreachable from the other nodes.
        distributor:
          receivers:
            otlp:
              protocols:
                grpc:
                  endpoint: 0.0.0.0:4317
                http:
                  endpoint: 0.0.0.0:4318

        ingester:
          max_block_duration: 30m

        compactor:
          compaction:
            # Matches Loki's 30d retention_period so traces and the logs that
            # link to them age out together.
            block_retention: 720h

        storage:
          trace:
            backend: s3
            s3:
              bucket: tempo
              endpoint: 192.168.2.29:9000
              access_key: $${MINIO_ACCESS_KEY}
              secret_key: $${MINIO_SECRET_KEY}
              forcepathstyle: true
              insecure: true
            wal:
              path: /var/tempo/wal

        # No metrics_generator block: the generator turns spans into RED
        # metrics and needs a remote_write target. It stays off by default
        # (processors are enabled per-tenant under `overrides`, not here), so
        # the block would only be noise.
        usage_report:
          reporting_enabled: false
        EOF

        destination = "local/tempo-config.yaml"
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }
  }
}
