### Restores one bucket from its GCS backup into SeaweedFS. Dispatch with
### `nomad job dispatch -meta bucket=<name> restore-s3`.
###
### Exit codes say what failed, because the operator token cannot read alloc
### logs: 1 copy, 2 check, 3 a directory missing on SeaweedFS (or its
### listing failed), 4 a GCS listing, 5 not one of the four durable buckets.
### No listing pipes into another command: without pipefail the pipe's exit
### status would be the last command's, and a failed listing would pass. A bucket with no prefix under minio/ was empty when backed up, so
### there is nothing to restore and the run exits 0.
###
### The marker flags, on both the GCS and the SeaweedFS side, keep
### OpenViking's empty directories, which it stores as zero-byte `dir/` keys. `rclone check` passes with every marker missing, so
### the one-way directory listing below is the check that catches it
### (spike:seaweedfs-cutover-openviking/2). Marker counts are not compared:
### a first flagged copy writes one per directory, a later sync only for empty
### ones.
job "restore-s3" {
  datacenters = ["localstack"]
  type        = "batch"
  namespace   = "default"

  parameterized {
    meta_required = ["bucket"]
  }

  group "restore" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    reschedule {
      attempts  = 0
      unlimited = false
    }

    restart {
      attempts = 0
      mode     = "fail"
    }

    task "restore" {
      driver = "podman"

      config {
        image        = "docker.io/rclone/rclone:1.75.2"
        network_mode = "host"
        entrypoint   = ["/bin/sh", "-c"]
        args = [<<-EOT
          set -u
          b="$NOMAD_META_bucket"
          case "$b" in
            openviking|registry|models|datalake) ;;
            *) echo "$b is not a durable bucket"; exit 5 ;;
          esac
          src="gcs:${gcs_bucket}/minio/$b/"
          dst="seaweedfs:$b"
          conf="--config /secrets/rclone.conf"
          prefixes=$(rclone lsf --dirs-only "gcs:${gcs_bucket}/minio/" $conf) || exit 4
          if ! echo "$prefixes" | grep -qx "$b/"; then
            echo "no backup of $b under minio/: nothing to restore"
            exit 0
          fi
          rclone copy "$src" "$dst" --create-empty-src-dirs --gcs-directory-markers --s3-directory-markers $conf || exit 1
          rclone check "$src" "$dst" $conf || exit 2
          rclone lsf -R --dirs-only --gcs-directory-markers "$src" $conf > /tmp/src-dirs || exit 4
          rclone lsf -R --dirs-only --s3-directory-markers "$dst" $conf > /tmp/dst-dirs || exit 3
          sort -o /tmp/src-dirs /tmp/src-dirs
          sort -o /tmp/dst-dirs /tmp/dst-dirs
          missing=$(comm -23 /tmp/src-dirs /tmp/dst-dirs)
          if [ -n "$missing" ]; then
            echo "directories missing on SeaweedFS:"
            echo "$missing"
            exit 3
          fi
          echo "restored $b"
          EOT
        ]
      }

      vault {}

      template {
        data = <<EOF
[seaweedfs]
type = s3
provider = SeaweedFS
access_key_id = {{ with secret "${seaweedfs_secret}" }}{{ .Data.data.access_key }}{{ end }}
secret_access_key = {{ with secret "${seaweedfs_secret}" }}{{ .Data.data.secret_key }}{{ end }}
endpoint = http://${seaweedfs_host}:8333

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
