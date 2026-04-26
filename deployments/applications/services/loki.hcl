job "loki" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "loki" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    network {
      port "http" {
        static = 3100
      }
      port "grpc" {
        static = 9095
      }
    }

    volume "loki_data" {
      type            = "host"
      source          = "loki_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    task "loki" {
      driver = "podman"
      user   = "root"

      vault {}

      service {
        name = "loki"
        port = "http"
        tags = ["http", "monitoring"]

        check {
          name     = "loki ready"
          type     = "http"
          port     = "http"
          path     = "/ready"
          method   = "GET"
          interval = "15s"
          timeout  = "3s"
        }
      }

      config {
        image = "docker.io/grafana/loki:3.4.2"
        args = [
          "-config.file=/local/loki-config.yaml",
          "-config.expand-env=true",
        ]
        ports        = ["http", "grpc"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "loki_data"
        destination = "/loki"
      }

      template {
        data = <<-EOF
        {{- with secret "${loki_minio_secret}" }}
        MINIO_ACCESS_KEY="{{ .Data.data.access_key }}"
        MINIO_SECRET_KEY="{{ .Data.data.secret_key }}"
        {{- end }}
        EOF

        destination = "secrets/minio.env"
        env         = true
      }

      template {
        data = <<-EOF
        auth_enabled: false

        server:
          http_listen_port: 3100
          grpc_listen_port: 9095
          log_level: info

        common:
          path_prefix: /loki
          replication_factor: 1
          ring:
            kvstore:
              store: inmemory

        memberlist:
          join_members: []

        ingester:
          chunk_idle_period: 2h
          max_chunk_age: 2h
          chunk_target_size: 1048576
          wal:
            enabled: true
            dir: /loki/wal

        schema_config:
          configs:
            - from: 2024-01-01
              store: tsdb
              object_store: s3
              schema: v13
              index:
                prefix: loki_index_
                period: 24h

        storage_config:
          tsdb_shipper:
            active_index_directory: /loki/index
            cache_location: /loki/index_cache
          aws:
            endpoint: 192.168.2.29:9000
            bucketnames: loki
            access_key_id: $${MINIO_ACCESS_KEY}
            secret_access_key: $${MINIO_SECRET_KEY}
            s3forcepathstyle: true
            insecure: true

        compactor:
          working_directory: /loki/compactor
          delete_request_store: s3
          retention_enabled: true

        limits_config:
          retention_period: 30d
          allow_structured_metadata: true

        analytics:
          reporting_enabled: false
        EOF

        destination = "local/loki-config.yaml"
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }
  }
}
