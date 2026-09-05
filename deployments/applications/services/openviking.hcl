### OpenViking: context store for agents, on radxa beside Bifrost.
###
### MinIO is reached with a STATIC key, not workload identity, and that is
### forced rather than chosen. `S3Config.validate_config` makes `access_key`
### and `secret_key` mandatory whenever `backend` is `s3`, and the Rust client
### behind AGFS builds `Credentials::new(ak, sk, None, ...)` with no session
### token, so STS credentials cannot be represented even if the validator were
### bypassed. There is deliberately NO `minio_iam_policy` named `openviking`:
### claim mode resolves a policy by the job id, so one would read as live while
### granting nothing. See the ticket's Q1.
###
### Rerank goes through Bifrost, which requires Bifrost >= 2.0.0: OpenViking's
### OpenAI-compatible rerank clients send `documents` as bare strings and
### 1.6.x rejected that shape at the gateway edge.
job "openviking" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "openviking" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${openviking_hostname}"
    }

    network {
      port "http" {
        static = 1933
      }
    }

    ### Holds ov.conf's workspace and RAGFS's local scratch. The vectors live
    ### in Postgres and the blobs in MinIO, so this is working state rather
    ### than the store itself.
    volume "openviking_data" {
      type      = "host"
      source    = "openviking_data"
      read_only = false
    }

    task "openviking" {
      driver = "podman"

      vault {}

      service {
        name    = "openviking"
        port    = "http"
        address = "${openviking_host}"

        tags = ["http", "context"]

        ### /ready, not /health: readiness is what reports the vector backend
        ### and AGFS actually opened. The dotted-path adapter resolves at
        ### startup, so a broken image fails here rather than on first query.
        check {
          name     = "openviking ready"
          type     = "http"
          port     = "http"
          path     = "/ready"
          method   = "GET"
          interval = "30s"
          timeout  = "5s"
        }
      }

      config {
        image        = "${openviking_image}"
        ports        = ["http"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "openviking_data"
        destination = "/app/.openviking"
      }

      env {
        OPENVIKING_CONFIG_FILE = "/secrets/ov.conf"
      }

      ### ov.conf. Credentials are interpolated by Nomad from Vault, which is
      ### why the whole file is a template rather than a committed artifact.
      ###
      ### Every secret path is under secret/data/default/openviking/: the
      ### nomad-workloads role grants a job read only under its own job id, so
      ### a path belonging to another job renders 403 and the task never
      ### starts.
      ###
      ### storage.vectordb.backend is a dotted import path, resolved by
      ### importlib at startup against the derived image. custom_params is a
      ### free-form dict on the OpenViking side and an extra=forbid model on
      ### ov-postgres's, so an unknown key here is a startup failure.
      ###
      ### server.oidc carries NO `identity` block: OpenViking's defaults map
      ### `sub`, and Vault's `groups` claim is an array that its scalar role
      ### mapping does not consume. jwks_uri is explicit so a first request
      ### does not depend on live discovery.
      template {
        data        = <<-EOF
        {
          "storage": {
            "workspace": "/app/.openviking/workspace",
            "agfs": {
              "backend": "s3",
              "s3": {
                "bucket": "openviking",
                "endpoint": "http://${minio_host}:9000",
                "region": "us-east-1",
                {{- with secret "${openviking_minio_secret}" }}
                "access_key": "{{ .Data.data.access_key }}",
                "secret_key": "{{ .Data.data.secret_key }}",
                {{- end }}
                "use_ssl": false,
                "use_path_style": true
              }
            },
            "vectordb": {
              "backend": "ov_postgres.adapter.PgVectorCollectionAdapter",
              "name": "context",
              "index_name": "default",
              "distance_metric": "cosine",
              "custom_params": {
                {{- with secret "${openviking_db_secret}" }}
                "dsn": "postgresql://{{ .Data.data.username }}:{{ .Data.data.password }}@${postgres_host}:5432/openviking",
                {{- end }}
                "schema": "openviking",
                "index_method": "flat"
              }
            }
          },
          "embedding": {
            "dense": {
              "provider": "openai",
              "model": "embark/embedding",
              "dimension": 768,
              "api_base": "http://${bifrost_host}:8080/v1",
              {{- with secret "${openviking_bifrost_secret}" }}
              "api_key": "{{ .Data.data.API_KEY }}"
              {{- end }}
            }
          },
          "rerank": {
            "provider": "openai",
            "model": "embark/reranker",
            "api_base": "http://${bifrost_host}:8080/v1",
            {{- with secret "${openviking_bifrost_secret}" }}
            "api_key": "{{ .Data.data.API_KEY }}",
            {{- end }}
            "timeout": 120
          },
          "server": {
            "host": "0.0.0.0",
            "port": 1933,
            "auth_mode": "oidc",
            "public_base_url": "https://${openviking_hostname_public}",
            "oidc": {
              "issuer": "${vault_oidc_issuer}",
              "client_id": "${openviking_client_id}",
              "audience": "${openviking_client_id}",
              "jwks_uri": "${vault_oidc_issuer}/.well-known/keys"
            }
          }
        }
        EOF
        destination = "secrets/ov.conf"
        change_mode = "restart"
      }

      resources {
        cpu        = 1000
        memory     = 1536
        memory_max = 2560
      }
    }
  }
}
