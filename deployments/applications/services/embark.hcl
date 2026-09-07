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
    # model.
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
        # kitops-ml, not jozu-ai: the project moved orgs and the old GHCR
        # namespace still serves images, frozen at v1.2.2. Querying it looks
        # like a current pin and is thirteen minors behind.
        image        = "ghcr.io/kitops-ml/kitops:v1.15.0"
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

        tags = ["http", "llm", "prometheus"]

        # /healthz, not /readyz, deliberately. Readiness stays false until
        # every model has warmed; a check on readiness would kill the task
        # mid-warm and restart it into the same warm, forever. That margin
        # gets thinner if TensorRT comes back, since its engine build adds
        # minutes.
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

        # GPU: seccomp blocks Jetson GPU ioctls on /dev/nvhost-* and /dev/nvmap
        security_opt = ["seccomp=unconfined", "label=disable"]

        # GPU: CUDA toolkit + cuDNN are on the host but not injected by
        # nvidia-container-runtime. Same list memex.hcl carries, and for the
        # same reason -- Dockerfile.embark's header says the runtime supplies
        # them, and on this node it does not.
        volumes = [
          "/usr/local/cuda-12.6/lib64:/usr/local/cuda/lib64:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn.so.9:/usr/lib/aarch64-linux-gnu/libcudnn.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_graph.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_graph.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_engines_precompiled.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_engines_precompiled.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_engines_runtime_compiled.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_engines_runtime_compiled.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_heuristic.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_heuristic.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_ops.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_ops.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_adv.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_adv.so.9:ro",
          "/usr/lib/aarch64-linux-gnu/libcudnn_cnn.so.9:/usr/lib/aarch64-linux-gnu/libcudnn_cnn.so.9:ro",
        ]
      }

      volume_mount {
        volume      = "embark_data"
        destination = "/var/lib/embark"
      }

      env {
        EMBARK_CONFIG_FILE = "/local/config.toml"
        EMBARK_CACHE_DIR   = "/var/lib/embark"

        # These three are what put the GPU in the container, and all three are
        # required. Without the first two, nvidia-container-runtime injects
        # neither libcuda.so.1 nor /dev/nvhost-gpu, and onnxruntime reports
        # CUDAExecutionProvider available, fails cudaSetDevice with error 35,
        # and falls back to CPU while the health check stays green. Without the
        # third, the bind-mounted CUDA libs sit off the linker's search path
        # and libcublas/libcudart go unresolved. memex.hcl sets the same three.
        NVIDIA_VISIBLE_DEVICES     = "all"
        NVIDIA_DRIVER_CAPABILITIES = "compute,utility"
        LD_LIBRARY_PATH            = "/usr/local/cuda/lib64"
        # Spans go to the node-local Alloy collector, which forwards to Tempo.
        # embark never learns where Tempo is, so moving or replacing the trace
        # backend is a collector change rather than a redeploy of every
        # producer.
        #
        EMBARK_TELEMETRY__ENABLED       = "true"
        EMBARK_TELEMETRY__OTLP_ENDPOINT = "${otlp_endpoint}"
        EMBARK_TELEMETRY__SERVICE_NAME  = "embark"

        # embark guards /metrics behind an `admin` key by default, and the
        # service is tagged "prometheus" so the shared consul_services scrape
        # job picks it up -- a job that cannot carry per-target credentials
        # (see the bifrost comment in infrastructure/services/prometheus.hcl).
        # Off rather than minting an admin key: `admin` outranks the `read`
        # role below and would also open the model routes, and /metrics is
        # three counters and latency histograms. Same posture as OpenViking,
        # and the ufw rules for port 8000 stay named-caller.
        EMBARK_AUTH__GUARD_METRICS = "false"
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

      # jetson-orin-nano has 7619 MB total and UNIFIED memory: there is no
      # separate VRAM, so every CUDA allocation ONNX Runtime makes comes out of
      # this same budget and is charged to this cgroup. That is what
      # `NvMapMemAllocInternalTagged ... error 12` (ENOMEM) means here -- the
      # GPU allocator asking this task's cgroup for pages it does not have.
      #
      # `memory` IS the enforced cap on this cluster, and there is deliberately
      # no `memory_max`. Nomad memory oversubscription is off at the server, so
      # the scheduler zeroes MemoryMaxMB in the allocation and the client sets
      # the cgroup from `memory` alone. A `memory_max` here reads as headroom
      # that does not exist: with memory=4096/memory_max=5120 the kernel showed
      # `memory.max = 4294967296` (4096 MiB), not 5120. Verified through podman
      # inspect and the container's own cgroup, not inferred.
      #
      # 5120, not 6144: the rest of the host (OS, nomad, alloy, node-exporter)
      # holds ~1019 MB, so 5120 leaves ~1480 MB and 6144 would leave ~460 MB.
      # Measured with `free -m` and the container cgroup on the node.
      resources {
        cpu    = 2000
        memory = 5120
      }
    }
  }
}
