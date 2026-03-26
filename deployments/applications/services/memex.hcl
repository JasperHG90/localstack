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
        args         = ["server", "start"]
        network_mode = "host"

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
MEMEX_SERVER__AUTH__ENABLED=true
{{- with secret "${memex_auth_secret}" }}
MEMEX_SERVER__AUTH__KEYS='[{"key":"{{ .Data.data.admin_key }}","policy":"admin","description":"Admin key"},{"key":"{{ .Data.data.writer_key }}","policy":"writer","vault_ids":["global"],"description":"Scoped writer"}]'
{{- end }}
MEMEX_SERVER__TRACING__ENABLED=true
MEMEX_SERVER__TRACING__ENDPOINT=http://${phoenix_host}:6006/v1/traces
{{ with secret "${memex_gemini_secret}" }}
GOOGLE_API_KEY={{ .Data.data.GOOGLE_API_KEY }}
{{ end }}
MEMEX_WORKERS=1
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
LD_LIBRARY_PATH=/usr/local/cuda/lib64
MEMEX_ONNX_PROVIDERS=CUDAExecutionProvider,CPUExecutionProvider
EOF

        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu    = 3500
        memory = 4500
      }
    }

  }
}
