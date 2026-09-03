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

      ### Keyless MinIO access. Field-by-field rationale is in
      ### docs/workload-identity.md; only what is specific to loki is here.
      ###
      ### No `vault {}`: the MinIO key was loki's only Vault use, so it needs
      ### no Vault access at all. `user = "root"` above is what lets the task
      ### read its own JWT.
      identity {
        name        = "minio"
        aud         = ["minio"]
        file        = true
        filepath    = "secrets/nomad_minio.jwt"
        ttl         = "1h"
        change_mode = "noop"
      }

      ### Loki reaches MinIO through aws-sdk-go v1, which has no way to be
      ### pointed at a non-AWS STS, so it cannot use tempo's provider. Instead
      ### the SDK runs local/minio-creds.sh, which performs the exchange and
      ### prints credentials; the SDK re-runs it when they expire.
      ###
      ### AWS_CONFIG_FILE is NOT optional and is the easiest thing to omit.
      ### Without it the SDK reads $HOME/.aws/config, which is /root/.aws/config
      ### here and does not exist, and every request fails with
      ### NoCredentialProviders. AWS_SDK_LOAD_CONFIG is what puts the config
      ### file on the SDK's list at all.
      ###
      ### AWS_WEB_IDENTITY_TOKEN_FILE must NOT be set, even though tempo sets
      ### it: aws-sdk-go checks it BEFORE the shared config and would pre-empt
      ### the helper, failing with "role ARN is not set".
      env {
        AWS_SDK_LOAD_CONFIG = "1"
        AWS_CONFIG_FILE     = "/local/aws-config"
        AWS_REGION          = "us-east-1"
      }

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

      ### The credential_process helper. Contract imposed by the SDK, not by
      ### us: "Version":1 is mandatory, stdout is capped at 8 KiB and the run
      ### at 60s, it is invoked through `sh -c`, and a non-zero exit surfaces
      ### as ProcessProviderExecutionError. So it prints the JSON and nothing
      ### else, and fails loudly rather than emitting a half-document.
      ###
      ### No RoleArn in the request: MinIO resolves the policy from the
      ### token's nomad_job_id claim, which is what makes the `loki` policy
      ### apply to loki alone.
      template {
        data        = <<-EOF
        #!/bin/sh
        set -eu
        jwt=$(cat /secrets/nomad_minio.jwt)
        body=$(wget -q -O - --post-data='' \
          "http://${minio_host}:9000/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&WebIdentityToken=$${jwt}")
        field() {
          printf '%s' "$${body}" | sed -n "s:.*<$1>\([^<]*\)</$1>.*:\1:p"
        }
        ak=$(field AccessKeyId)
        sk=$(field SecretAccessKey)
        st=$(field SessionToken)
        ex=$(field Expiration)
        if [ -z "$${ak}" ] || [ -z "$${sk}" ] || [ -z "$${st}" ] || [ -z "$${ex}" ]; then
          echo "minio-creds: STS response missing a credential field" >&2
          exit 1
        fi
        printf '{"Version":1,"AccessKeyId":"%s","SecretAccessKey":"%s","SessionToken":"%s","Expiration":"%s"}\n' \
          "$${ak}" "$${sk}" "$${st}" "$${ex}"
        EOF
        destination = "local/minio-creds.sh"
        perms       = "0755"
      }

      ### Points the SDK at the helper. The path here and AWS_CONFIG_FILE above
      ### must stay identical.
      template {
        data        = <<-EOF
        [default]
        credential_process = /local/minio-creds.sh
        EOF
        destination = "local/aws-config"
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
