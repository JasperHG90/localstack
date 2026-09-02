job "embark" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "embark" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${embark_hostname}"
    }

    network {
      port "http" {
        static = 8000
      }
    }

    # One volume, two jobs. It holds the unpacked model artifacts under
    # artifacts/ AND embark's own cache, which the image declares a volume and
    # embark's docs call not optional: without it a restart re-downloads every
    # model, and on a Jetson it also rebuilds the TensorRT engine, which takes
    # minutes.
    volume "embark_data" {
      type            = "host"
      source          = "embark_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    # Pulls each ModelKit out of the cluster registry before embark starts.
    # embark resolves every model reference at startup and refuses to start on
    # a missing one, so this has to be a prestart task rather than a sidecar.
    task "model-pull" {
      driver = "podman"
      # The kitops image runs as uid 1001 and cannot write a host volume owned
      # by root. Same reason loki, tempo and grafana run as root here.
      user = "root"

      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      vault {}

      volume_mount {
        volume      = "embark_data"
        destination = "/var/lib/embark"
      }

      config {
        image        = "ghcr.io/jozu-ai/kitops:v1.2.2"
        entrypoint   = ["/bin/sh"]
        args         = ["/local/pull.sh"]
        network_mode = "host"
      }

      # kit reads credentials from a Docker-style auth file in its config
      # directory. Rendering it directly skips `kit login` entirely, which
      # matters: login takes the password as an argument or on stdin, and this
      # way it never becomes a process argument at all.
      template {
        data = <<-EOF
        {{- with secret "${registry_auth_secret}" }}
        {"auths":{"${registry_host}":{"auth":"{{ printf "%s:%s" .Data.data.username .Data.data.password | base64Encode }}"}}}
        {{- end }}
        EOF

        destination = "secrets/kit/credentials.json"
      }

      # services/embark/pull.sh, verbatim. The logic is a real file in the
      # repo rather than a string built in Terraform, so it can be read,
      # shellchecked and run on its own.
      template {
        data = <<-EOF
${pull_script}
        EOF

        destination = "local/pull.sh"
        perms       = "0755"
      }

      # The work list pull.sh reads: one "<name> <registry-reference>" per
      # line, generated from services/embark/models.json by services.tf. Data,
      # not code -- the same file drives what embark is told to serve, so the
      # two cannot drift.
      template {
        data = <<-EOF
${models_list}
        EOF

        destination = "local/models.txt"
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }

    task "embark" {
      driver = "podman"
      # The mkdir host-volume plugin creates embark_data as root:root 0700
      # and this image runs as uid 10001, so without this the task can neither
      # read the artifacts model-pull just unpacked nor write its own cache.
      # Same reason loki, tempo, grafana, prometheus, nats and hermes set it.
      user = "root"

      # Named role, not the default: it mints the Redis cache credential from
      # `redis/creds/cache-embark`. Naming a role REPLACES `nomad-workloads`
      # rather than adding to it, so that policy is attached alongside in
      # redis_secrets_engine.tf -- without it this task would lose the KV
      # reads below. The job id must stay `embark`, since the role is bound to
      # that claim.
      vault {
        role = "redis-cache-embark"
      }

      service {
        name    = "embark"
        port    = "http"
        address = "${embark_host}"

        tags = ["http", "llm"]

        # /healthz, not /readyz, deliberately. Readiness stays false until
        # every model has warmed, and on a Jetson that includes a TensorRT
        # engine build -- a check on readiness would kill the task mid-build
        # and restart it into the same build, forever.
        check {
          name     = "embark alive"
          type     = "http"
          port     = "http"
          path     = "/healthz"
          method   = "GET"
          interval = "15s"
          timeout  = "3s"
        }
      }

      config {
        image        = "${embark_image}"
        ports        = ["http"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "embark_data"
        destination = "/var/lib/embark"
      }

      env {
        EMBARK_CONFIG_FILE = "/local/config.toml"
        EMBARK_CACHE_DIR   = "/var/lib/embark"
        # Spans go to the node-local Alloy collector, which forwards to Tempo.
        # embark never learns where Tempo is, so moving or replacing the trace
        # backend is a collector change rather than a redeploy of every
        # producer.
        #
        # PREREQUISITE: that collector does not exist yet. Today's Alloy is
        # the log shipper only and runs no OTLP receiver, so spans sent here
        # go nowhere until O1-observability-otlp-llm-routing lands. Harmless
        # while this job stays commented out in services.tf; check it before
        # uncommenting.
        EMBARK_TELEMETRY__ENABLED       = "true"
        EMBARK_TELEMETRY__OTLP_ENDPOINT = "${otlp_endpoint}"
        EMBARK_TELEMETRY__SERVICE_NAME  = "embark"
      }

      # EMBARK_MODELS is JSON, so it cannot go in the `env` block above: its
      # double quotes would terminate the HCL string. An env FILE takes it
      # single-quoted instead, the same shape memex uses for its own JSON
      # settings. Merges per key with config.toml rather than replacing it,
      # and points at what model-pull unpacked.
      template {
        data = <<-EOF
        EMBARK_MODELS='${embark_models}'
        EOF

        destination = "local/models.env"
        env         = true
      }

      # Auth ships ON and embark refuses to start when it is enabled with no
      # keys, so this is required rather than optional. Kept out of
      # config.toml on embark's own advice: a config file is the copy that
      # gets committed by accident.
      template {
        data = <<-EOF
        {{- with secret "${embark_auth_secret}" }}
        EMBARK_AUTH__KEYS='[{"name":"cluster","secret":"{{ .Data.data.api_key }}","role":"read"}]'
        {{- end }}
        EOF

        destination = "secrets/auth.env"
        env         = true
      }

      # Redis response cache. The credential is minted per render from the
      # Redis secrets engine and revoked on lease expiry -- `.Data.username`,
      # not `.Data.data.username`, because that engine is not KV v2.
      #
      # The TTL is 15m by design (redis_secrets_engine.tf): dynamic users live
      # only in Redis's memory, so any restart of the redis task wipes them
      # while Vault still thinks the leases are good. A short TTL bounds that
      # desync. change_mode restart means a renewed lease restarts embark
      # rather than leaving it holding a revoked password.
      template {
        data = <<-EOF
        {{- with secret "redis/creds/cache-embark" }}
        EMBARK_CACHE__URL='redis://{{ .Data.username }}:{{ .Data.password }}@${redis_host}:6379/0'
        {{- end }}
        EOF

        destination = "secrets/cache.env"
        env         = true
        change_mode = "restart"
      }

      template {
        data        = <<-EOF
${config_toml}
        EOF
        destination = "local/config.toml"
        change_mode = "restart"
      }

      resources {
        cpu        = 2000
        memory     = 2048
        memory_max = 3072
      }
    }
  }
}
