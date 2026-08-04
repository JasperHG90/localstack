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

      ### v0.16.0 could not read PG17+. PostgreSQL 17 moved the checkpoint
      ### counters out of `pg_stat_bgwriter` into the new `pg_stat_checkpointer`
      ### view, and v0.16.0 still issues the flat pre-17 query, so against this
      ### PG18 server every scrape logged
      ### `collector failed name=stat_bgwriter err="pq: column
      ### "checkpoints_timed" does not exist"` and Postgres logged the matching
      ### ERROR — 3454 times in one allocation's lifetime. Upstream fixed it in
      ### v0.17.0 (PR #1072); v0.20.1 is CI-tested against PG18.
      ###
      ### `--collector.stat_checkpointer` is required, not optional: the
      ### collector that now owns those counters ships DISABLED by default, so
      ### upgrading alone trades the error spam for silently missing checkpoint
      ### metrics. The counters also change name — `pg_stat_bgwriter_
      ### checkpoints_timed_total` becomes `pg_stat_checkpointer_num_timed_
      ### total`, and so on. Nothing in this repo graphs or alerts on the old
      ### names, so no dashboard needed updating; check that again before
      ### bumping further.
      config {
        image        = "docker.io/prometheuscommunity/postgres-exporter:v0.20.1"
        ports        = ["exporter"]
        network_mode = "host"
        args         = ["--collector.stat_checkpointer"]
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
