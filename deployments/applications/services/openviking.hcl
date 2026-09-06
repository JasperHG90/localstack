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

      ### ov.conf. The document itself is services/openviking/ov.conf.json,
      ### parsed and re-injected by services.tf's `openviking_ov_conf` local,
      ### so a syntax error fails at plan time rather than at startup.
      ###
      ### The four assignments below bind each secret to its OWN variable,
      ### which is what the placeholders in that file name. Nested `with secret`
      ### scopes would NOT work: each one rebinds the dot, so every
      ### `.Data.data.*` reference would resolve against the innermost secret
      ### and silently read the wrong credential.
      ###
      ### Each path is under this job's own prefix: the nomad-workloads role
      ### grants a job read only on secret/data/<namespace>/<job_id>/*, so
      ### another job's path renders 403 and the task never starts.
      ###
      ### NOTE: this whole template.data block is a live Nomad template. Do not
      ### write a literal double-curly-brace action in a comment here; it gets
      ### parsed, not read.
      template {
        data        = <<-EOF
        {{- $minio := secret "${openviking_minio_secret}" -}}
        {{- $db := secret "${openviking_db_secret}" -}}
        {{- $bifrost := secret "${openviking_bifrost_secret}" -}}
        {{- $root := secret "${openviking_root_key_secret}" -}}
        ${ov_conf}
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
