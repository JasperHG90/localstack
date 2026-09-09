job "memex" {
  datacenters = ["localstack"]
  type        = "service"

  group "memex" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "jetson-orin-nano"
    }

    volume "memex_data_volume" {
      type            = "host"
      source          = "memex_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    network {
      port "http" {
        static = 8000
      }
    }

    task "db-migrate" {
      driver = "podman"

      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      volume_mount {
        volume      = "memex_data_volume"
        destination = "/cache"
      }

      config {
        image        = "ghcr.io/jasperhg90/memex-jetson:${memex_version}"
        args         = ["database", "upgrade"]
        network_mode = "host"
        force_pull   = true
      }

      vault {}

      template {
        data = <<EOF
MEMEX_SERVER__META_STORE__TYPE=postgres
MEMEX_SERVER__META_STORE__INSTANCE__HOST=${postgres_host}
MEMEX_SERVER__META_STORE__INSTANCE__PORT=5432
MEMEX_SERVER__META_STORE__INSTANCE__DATABASE=memex
{{ with secret "${memex_postgres_secret}" }}
MEMEX_SERVER__META_STORE__INSTANCE__USER={{ .Data.data.username }}
MEMEX_SERVER__META_STORE__INSTANCE__PASSWORD={{ .Data.data.password }}
{{ end }}
EOF

        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }

    task "memex" {
      driver = "podman"

      service {
        name    = "memex"
        port    = "http"
        address = "${memex_host}"

        tags = ["http", "memex"]

        check {
          type     = "http"
          path     = "/api/v1/health"
          interval = "10s"
          timeout  = "2s"
        }
      }

      volume_mount {
        volume      = "memex_data_volume"
        destination = "/cache"
      }

      config {
        image        = "ghcr.io/jasperhg90/memex-jetson:${memex_version}"
        args         = ["--debug", "server", "start"]
        network_mode = "host"
        force_pull   = true

        # GPU: seccomp blocks Jetson GPU ioctls on /dev/nvhost-* and /dev/nvmap
        security_opt = ["seccomp=unconfined", "label=disable"]

        # GPU: CUDA toolkit + cuDNN are on the host but not injected by nvidia-container-runtime
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

      vault {}

      template {
        data = <<EOF
MEMEX_SERVER__CACHE_DIR=/cache/memex
MEMEX_SERVER__FILE_STORE__TYPE=s3
MEMEX_SERVER__FILE_STORE__BUCKET=memex
MEMEX_SERVER__FILE_STORE__ROOT=
MEMEX_SERVER__FILE_STORE__ENDPOINT_URL=http://${minio_host}:9000
MEMEX_SERVER__FILE_STORE__REGION=us-east-1
{{ with secret "${memex_minio_secret}" }}
MEMEX_SERVER__FILE_STORE__ACCESS_KEY_ID={{ .Data.data.access_key }}
MEMEX_SERVER__FILE_STORE__SECRET_ACCESS_KEY={{ .Data.data.secret_key }}
{{ end }}
MEMEX_SERVER__META_STORE__TYPE=postgres
MEMEX_SERVER__META_STORE__INSTANCE__HOST=${postgres_host}
MEMEX_SERVER__META_STORE__INSTANCE__PORT=5432
MEMEX_SERVER__META_STORE__INSTANCE__DATABASE=memex
{{ with secret "${memex_postgres_secret}" }}
MEMEX_SERVER__META_STORE__INSTANCE__USER={{ .Data.data.username }}
MEMEX_SERVER__META_STORE__INSTANCE__PASSWORD={{ .Data.data.password }}
{{ end }}
MEMEX_SERVER__META_STORE__POOL_SIZE=20
MEMEX_SERVER__META_STORE__MAX_OVERFLOW=30
# The key list is services/memex/auth_keys.json (parsed and re-injected by
# services.tf's memex_auth_keys local): three entries, each carrying a
# Nomad template placeholder for the actual key material (see that file).
# Those placeholders are opaque strings to Terraform, which round-trips them
# unchanged, and are only resolved by Nomad's own template engine here,
# inside this `with secret` scope, at render time on the client.
#
# NOTE: this whole template.data block is a live Nomad/consul-template
# source, not HCL — a `#` line is plain text here, not a comment. Never
# write a literal double-curly-brace template action in one of these
# lines (as prose or otherwise); it gets parsed, not read.
MEMEX_SERVER__AUTH__ENABLED=true
{{- with secret "${memex_auth_secret}" }}
MEMEX_SERVER__AUTH__KEYS='${memex_auth_keys}'
{{- end }}
# Two trusted issuers, selected by the token's `iss`. Neither sets
# default_policy, so a token that verifies but matches no rule is refused
# rather than silently downgraded. The provider list and grant rules are
# defined in services/memex/auth_oidc.json (parsed and re-injected by
# services.tf's memex_auth_oidc local), not inline here — see that file for
# ELEMENT 1 (Nomad workloads: hermes, leo-consumer) and ELEMENT 2 (Vault
# humans, whose `audience` is the CLIENT ID, not "memex": Vault signs only
# the id_token, and an id_token's `aud` carries the client id).
MEMEX_SERVER__AUTH__OIDC='${memex_auth_oidc}'
MEMEX_SERVER__TRACING__ENABLED=true
# The node's own Alloy, which batches and forwards to Tempo. This used to be
# phoenix on 192.168.2.29:6006, and phoenix was retired. Tracing to loopback is
# what Alloy's OTLP receiver is bound for: a producer never learns where the
# trace backend lives, and nothing off-node can reach the receiver.
MEMEX_SERVER__TRACING__ENDPOINT=http://127.0.0.1:4320/v1/traces
MEMEX_SERVER__MEMORY__REFLECTION__MIN_PRIORITY=0.8
MEMEX_SERVER__MEMORY__INBOX_ROUTER__ENABLED=true
MEMEX_SERVER__MEMORY__INBOX_ROUTER__MIN_DECISIONS_BEFORE_AUTO_APPLY=30
MEMEX_SERVER__DEFAULT_MODEL__MODEL=openai/ollama/deepseek-v4-flash:0731
MEMEX_SERVER__DEFAULT_MODEL__BASE_URL=http://${bifrost_host}:8080/v1
MEMEX_SERVER__DEFAULT_MODEL__API_KEY={{ with secret "${bifrost_key_secret}" }}{{ .Data.data.API_KEY }}{{ end }}
# Per-stage model routing, both via the Bifrost gateway. Extraction (~20% of
# token volume, wants strong structured output) runs on fast Gemini flash-lite;
# reflection (~71% of token volume) stays on flat-rate Ollama. Other stages
# (contradiction, document, vault_summary) inherit DEFAULT_MODEL (Ollama).
MEMEX_SERVER__MEMORY__EXTRACTION__MODEL__MODEL=openai/gemini/gemini-3.1-flash-lite
MEMEX_SERVER__MEMORY__EXTRACTION__MODEL__BASE_URL=http://${bifrost_host}:8080/v1
MEMEX_SERVER__MEMORY__EXTRACTION__MODEL__API_KEY={{ with secret "${bifrost_key_secret}" }}{{ .Data.data.API_KEY }}{{ end }}
MEMEX_SERVER__MEMORY__REFLECTION__MODEL__MODEL=openai/ollama/deepseek-v4-flash:0731
MEMEX_SERVER__MEMORY__REFLECTION__MODEL__BASE_URL=http://${bifrost_host}:8080/v1
MEMEX_SERVER__MEMORY__REFLECTION__MODEL__API_KEY={{ with secret "${bifrost_key_secret}" }}{{ .Data.data.API_KEY }}{{ end }}
MEMEX_WORKERS=1
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
LD_LIBRARY_PATH=/usr/local/cuda/lib64
MEMEX_ONNX_PROVIDERS=CUDAExecutionProvider,CPUExecutionProvider
MEMEX_SERVER__MEMORY__RETRIEVAL__RERANKER_BATCH_SIZE=8
MEMEX_SERVER__EMBEDDING_BATCH_SIZE=16
MEMEX_SERVER__RERANKER_MAX_CONCURRENCY=2
MEMEX_SERVER__EMBEDDING_MAX_CONCURRENCY=2
MEMEX_SERVER__NER_MAX_CONCURRENCY=2
MEMEX_SERVER__NLI_MAX_CONCURRENCY=2
# page_index text-splitting: Jetson-tuned. Force header-less docs to chunk the
# scan (default 20k lets an 11k doc go single-call). STRATEGY is the union
# discriminator and must be set whenever any sub-field below is overridden.
MEMEX_SERVER__MEMORY__EXTRACTION__TEXT_SPLITTING__STRATEGY=page_index
MEMEX_SERVER__MEMORY__EXTRACTION__TEXT_SPLITTING__SCAN_CHUNK_SIZE_TOKENS=3000
MEMEX_SERVER__MEMORY__ENTITY_MAINTENANCE__SCAN_ENABLED=true
MEMEX_ONNX_GPU_MEM_LIMIT=4294967296
EOF

        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu        = 3500
        memory     = 6500
        memory_max = 7000
      }
    }

  }
}
