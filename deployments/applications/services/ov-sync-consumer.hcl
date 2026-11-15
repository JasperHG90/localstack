### ov-sync-consumer: reads filer events on the ov-sync bucket from JetStream
### and makes OpenViking match the bucket. Source and tests are in
### applications/ov-sync-consumer/. The receiver that publishes the events
### runs inside the seaweedfs job (infrastructure root).
###
### Runs on radxa beside NATS and OpenViking. It serves nothing, so it has no
### port, no service and no firewall rule.
job "ov-sync-consumer" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "ov-sync-consumer" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    task "consumer" {
      driver = "podman"

      ### This job's own JWT role, which may mint its OpenViking identity
      ### token and nothing else's (infrastructure root, machine_roles.tf).
      vault {
        role = "ov-sync-consumer"
      }

      ### Keyless SeaweedFS access, as tempo does it
      ### (docs/how-to/give-a-job-keyless-seaweedfs-access.md). The task runs
      ### as root, the image's default, so it can read the JWT.
      identity {
        name        = "seaweedfs"
        aud         = ["seaweedfs"]
        file        = true
        filepath    = "secrets/nomad_seaweedfs.jwt"
        ttl         = "1h"
        change_mode = "noop"
      }

      ### Every read of this path mints a new token, so a template that
      ### restarted on change would restart the task on every poll. The
      ### consumer reads the file on every request instead.
      template {
        data        = <<-EOT
        {{- with secret "identity/oidc/token/openviking-ov-sync-consumer" }}{{ .Data.token }}{{ end }}
        EOT
        destination = "secrets/ov_token"
        change_mode = "noop"
      }

      template {
        data        = <<-EOT
        ${prefixes}
        EOT
        destination = "local/prefixes.json"
      }

      env {
        NATS_URL                    = "${nats_url}"
        OV_URL                      = "http://${openviking_host}:1933"
        OV_TOKEN_FILE               = "/secrets/ov_token"
        OV_SYNC_MAP_FILE            = "/local/prefixes.json"
        S3_ENDPOINT                 = "${s3_host}:8333"
        S3_BUCKET                   = "ov-sync"
        AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_seaweedfs.jwt"
        AWS_ROLE_ARN                = "arn:aws:iam::role/ov-sync-consumer"

        ### Each OpenViking write regenerates folder summaries with one VLM
        ### call, so these two bound that cost: at most POOL_SIZE requests in
        ### flight, and at most RATE_PER_SECOND events started each second.
        POOL_SIZE       = "4"
        RATE_PER_SECOND = "2"

        CATCHUP_INTERVAL = "15m"
        GOMEMLIMIT       = "100MiB"
      }

      config {
        image        = "${ov_sync_consumer_image}"
        args         = ["consumer"]
        network_mode = "host"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
