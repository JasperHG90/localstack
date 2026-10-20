job "backup-minio" {
  datacenters = ["localstack"]
  type        = "batch"
  namespace   = "default"

  periodic {
    crons            = ["0 3 * * *"]
    time_zone        = "Europe/Amsterdam"
    prohibit_overlap = true
  }

  group "backup" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    task "sync" {
      driver = "podman"

      config {
        image        = "docker.io/rclone/rclone:latest"
        network_mode = "host"
        entrypoint   = ["/bin/sh", "-c"]
        ### Every bucket is attempted, and one failed sync still fails the run.
        ### loki and tempo keep 30 days and are not backed up.
        ### OpenViking stores each directory as a zero-byte key ending in `/`.
        ### Without the two marker flags rclone drops them, empty directories
        ### vanish on restore, and `rclone check` still passes
        ### (spike:seaweedfs-cutover-openviking/2).
        args = [<<-EOT
          rc=0
          rclone sync minio:openviking gcs:${gcs_bucket}/minio/openviking/ --create-empty-src-dirs --gcs-directory-markers --config /secrets/rclone.conf || rc=1
          rclone sync minio:registry gcs:${gcs_bucket}/minio/registry/ --create-empty-src-dirs --gcs-directory-markers --config /secrets/rclone.conf || rc=1
          rclone sync minio:models gcs:${gcs_bucket}/minio/models/ --create-empty-src-dirs --gcs-directory-markers --config /secrets/rclone.conf || rc=1
          rclone sync minio:datalake gcs:${gcs_bucket}/minio/datalake/ --create-empty-src-dirs --gcs-directory-markers --config /secrets/rclone.conf || rc=1
          exit $rc
          EOT
        ]
      }

      vault {}

      template {
        data = <<EOF
[minio]
type = s3
provider = Minio
access_key_id = {{ with secret "${minio_secret}" }}{{ .Data.data.access_key }}{{ end }}
secret_access_key = {{ with secret "${minio_secret}" }}{{ .Data.data.secret_key }}{{ end }}
endpoint = http://${minio_host}:9000

[gcs]
type = google cloud storage
service_account_file = /secrets/gcs-key.json
bucket_policy_only = true
EOF

        destination = "secrets/rclone.conf"
      }

      template {
        data        = <<EOF
{{ with secret "${gcs_secret}" }}{{ .Data.data.service_account_json }}{{ end }}
EOF
        destination = "secrets/gcs-key.json"
      }

      resources {
        cpu    = 1000
        memory = 512
      }
    }
  }
}
