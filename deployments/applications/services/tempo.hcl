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

      ### Keyless MinIO access. The field-by-field rationale lives in
      ### docs/workload-identity.md, under "The `identity`-stanza and
      ### audience convention". Only what is specific to tempo is here.
      ###
      ### There is no `vault {}` block because the MinIO key was this job's
      ### only Vault use, so tempo needs no Vault access at all. `user =
      ### "root"` above is safe: the documented hazard is a NON-root user,
      ### where Nomad's chown puts the JWT out of the task's reach.
      identity {
        name        = "minio"
        aud         = ["minio"]
        file        = true
        filepath    = "secrets/nomad_minio.jwt"
        ttl         = "1h"
        change_mode = "noop"
      }

      ### These two send tempo down minio-go's web-identity path.
      ###
      ### THE SCHEME ON TEST_IAM_ENDPOINT IS LOAD-BEARING and deliberately
      ### unlike the schemeless `endpoint:` the storage config further down
      ### this file gives the S3 client. Drop the scheme here and minio-go
      ### makes no STS call at all: no error, no log line, just silent
      ### anonymous S3. Verified by probing the pinned image in plan review.
      ###
      ### AWS_ROLE_ARN is deliberately ABSENT. Setting it would send a
      ### RoleArn and select role-policy mode, pinning every workload on the
      ### target to one shared policy. Omitting it sends none, which is
      ### claim mode, which is what makes the `tempo` policy apply to tempo
      ### alone.
      env {
        AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_minio.jwt"
        TEST_IAM_ENDPOINT           = "http://192.168.2.29:9000"
      }

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
        # No -config.expand-env: nothing in the config template interpolates
        # a variable any more, now that the MinIO keys are gone.
        args         = ["-config.file=/local/tempo-config.yaml"]
        ports        = ["http", "grpc", "otlp_grpc", "otlp_http"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "tempo_data"
        destination = "/var/tempo"
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
