job "backup-postgres" {
  datacenters = ["localstack"]
  type        = "batch"
  namespace   = "default"

  periodic {
    crons            = ["0 2 * * *"]
    time_zone        = "Europe/Amsterdam"
    prohibit_overlap = true
  }

  group "backup" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "firebat"
    }

    task "pgdump" {
      driver = "podman"

      lifecycle {
        hook = "prestart"
      }

      config {
        image        = "docker.io/library/postgres:18"
        network_mode = "host"
        entrypoint   = ["/bin/sh", "-c"]
        args         = ["pg_dumpall -h ${postgres_host} | gzip > /alloc/data/pgdumpall-$(date +%Y-%m-%d).sql.gz"]
      }

      vault {}

      template {
        data = <<EOF
PGUSER="{{ with secret "${postgres_secret}" }}{{ .Data.data.username }}{{ end }}"
PGPASSWORD="{{ with secret "${postgres_secret}" }}{{ .Data.data.password }}{{ end }}"
EOF

        destination = "secrets/pg.env"
        env         = true
      }

      resources {
        cpu    = 1000
        memory = 512
      }
    }

    task "upload" {
      driver = "podman"

      config {
        image      = "docker.io/rclone/rclone:latest"
        entrypoint = ["/bin/sh", "-c"]
        args       = ["rclone copy /alloc/data/ :gcs:${gcs_bucket}/postgres/ --gcs-service-account-file /secrets/gcs-key.json"]
      }

      vault {}

      template {
        data        = <<EOF
{{ with secret "${gcs_secret}" }}{{ .Data.data.service_account_json }}{{ end }}
EOF
        destination = "secrets/gcs-key.json"
      }

      resources {
        cpu    = 500
        memory = 256
      }
    }
  }
}
