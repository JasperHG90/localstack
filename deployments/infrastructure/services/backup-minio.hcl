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
    task "sync" {
      driver = "podman"

      config {
        image        = "docker.io/rclone/rclone:latest"
        network_mode = "host"
        entrypoint   = ["/bin/sh", "-c"]
        args         = ["rclone sync minio:memex gcs:${gcs_bucket}/minio/memex/ --config /secrets/rclone.conf"]
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
