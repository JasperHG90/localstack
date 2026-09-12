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

          ### Covers what bypassing the image entrypoint gave up. That script
          ### polled /health for 120s and exited non-zero if the server never
          ### became ready, which failed the task and let the restart policy
          ### act. Without this stanza a server that starts but never readies
          ### is deregistered and left running. Four intervals is the same 120s
          ### budget, and grace covers the model and backend warm.
          ###
          ### Not the same behavior, deliberately: the entrypoint checked once,
          ### at startup, and never again. This also restarts a task whose
          ### /ready flaps for two minutes in steady state.
          check_restart {
            limit = 4
            grace = "60s"
          }
        }
      }

      ### `command` and `args` land as the container command, so the image's
      ### `openviking-entrypoint` receives them and `exec`s them on its first
      ### non-bot argument. Three things it would have done are given up with
      ### that exec: writing the config, which the template below already did;
      ### polling /health, which `check_restart` above now covers; and honoring
      ### `OPENVIKING_SERVER_HOST`, `OPENVIKING_SERVER_PORT` and
      ### `OPENVIKING_WITH_BOT`, which are dead here since the flags are
      ### written out. Those flags are what the entrypoint would have passed.
      ###
      ### `python -m`, not the `ov-retrieval-server` console script. A --target
      ### install puts that script under site-packages/bin, which is not on
      ### PATH, and stamps it with the building interpreter rather than the
      ### venv's. Naming the venv python resolves both.
      config {
        image        = "${openviking_image}"
        ports        = ["http"]
        network_mode = "host"
        command      = "/app/.venv/bin/python"
        args         = ["-m", "ov_ext", "--host", "0.0.0.0", "--port", "1933", "--with-bot"]
      }

      volume_mount {
        volume      = "openviking_data"
        destination = "/app/.openviking"
      }

      ### Web Studio mounts itself from whatever this names, and skips the
      ### mount when the directory holds no index.html (server/app.py). There
      ### is no config-file switch. Pointing it at a path that does not exist
      ### is how the bundle is turned off, and it takes `/` with it: the root
      ### redirect is registered inside the same block. Studio always answered
      ### without a token, so the api hostname served it to anyone who reached
      ### the edge long before oauth2-proxy was deleted. Unmounting is what
      ### closes that, not the proxy's removal.
      ###
      ### The OV_RETRIEVAL_ block restates ov-retrieval's own defaults rather
      ### than inheriting them. Cost is one reason: `pool_factor` multiplies
      ### how many candidates the hierarchical descent and the Bifrost rerank
      ### both run over, and this task holds one CPU and 1536 MB. None of these
      ### has been measured on this hardware, so pinning them keeps a future
      ### upstream default from moving the retrieval path without a commit
      ### here.
      ###
      ### `mmr_lambda` is pinned for a second reason: the diversity pass runs
      ### only when it is below 1.0, so a default that moved to 1.0 would turn
      ### the pass off while `OV_RETRIEVAL_MMR_ENABLED` still read as on.
      ###
      ### `mmr_embedding_weight` and `mmr_entity_weight` are left alone. They
      ### split one similarity blend between cosine and tag overlap, so a
      ### change to either shifts ranking within the pass rather than switching
      ### anything off or multiplying any cost.
      env {
        OPENVIKING_CONFIG_FILE    = "/secrets/ov.conf"
        OPENVIKING_WEB_STUDIO_DIR = "/nonexistent"

        OV_RETRIEVAL_KEYWORD_ENABLED = "true"
        OV_RETRIEVAL_KEYWORD_WEIGHT  = "0.7"
        OV_RETRIEVAL_RRF_K           = "60"
        OV_RETRIEVAL_POOL_FACTOR     = "4"
        OV_RETRIEVAL_MMR_ENABLED     = "true"
        OV_RETRIEVAL_MMR_LAMBDA      = "0.7"
        # Cap the number of calls that can go out to the reranking service
        # to speed up search. These settings reduce the overhead on the
        # reranker model
        OV_RETRIEVAL_RERANK_POOLING       = "true"
        OV_RETRIEVAL_RERANK_MAX_CALLS     = "4"
        OV_RETRIEVAL_RERANK_MAX_DOCUMENTS = "20"
        OV_RETRIEVAL_RERANK_FINAL         = "true"
        # These settings enable reflection
        OV_REFLECT_MODEL            = "ollama/deepseek-v4-flash:0731"
        OV_REFLECT_DELTAS_SCHEMA    = "openviking"
        OV_REFLECT_ENABLED          = "true"
        OV_REFLECT_USER_ID          = "jasper"
        OV_REFLECT_ACCOUNT_ID       = "lab"
        OV_REFLECT_LOCK             = "process" # postgres for db lock
        OV_REFLECT_INTERVAL_SECONDS = "3600"
        OV_REFLECT_DRY_RUN          = "false"
        OV_REFLECT_BATCH_LIMIT      = "20"
        OV_REFLECT_NEIGHBOUR_LIMIT  = "5"
        OV_REFLECT_TAIL_SAMPLE      = "3"
      }

      # Reflect lock DSN carries a vault-rendered password for postgresa
      # template {
      #   data        = <<-EOF
      #   {{- $db := secret "${openviking_db_secret}" -}}
      #   OV_REFLECT_LOCK_DSN=postgresql://{{ $db.Data.data.username }}:{{ $db.Data.data.password }}@\{postgres_host\}:5432/openviking
      #   EOF
      #   destination = "secrets/reflect.env"
      #   env         = true
      #   change_mode = "restart"
      # }

      ### Reflection's delta store.
      ###
      ### ov-ext opens its OWN pool rather than borrowing the backend's: capture
      ### installs during ov_ext.install(), before OpenViking's engine exists,
      ### and neither package imports the other.
      ###
      ### Without this, reflection still runs, but it feeds the model whole
      ### memory files instead of the diff. Measured upstream: a 23 KB memory
      ### with two edited lines is 23,003 characters whole and 83 as a delta.
      ### Whole files are also why a failing batch is lost rather than retried:
      ### only the delta path records reflected_at.
      ###
      ### Its own destination, NOT the secrets/reflect.env the commented lock
      ### template above names. Two templates writing one file leaves the last
      ### one to win and drops the other's variable with nothing logged.
      ###
      ### A file rather than the env block above, because it carries the
      ### postgres password: env lands in the jobspec Nomad stores and
      ### `nomad job inspect` prints; secrets/ is a per-alloc tmpfs.
      template {
        data        = <<-EOF
        {{- $db := secret "${openviking_db_secret}" -}}
        OV_REFLECT_DELTAS_DSN=postgresql://{{ $db.Data.data.username }}:{{ $db.Data.data.password }}@${postgres_host}:5432/openviking
        EOF
        destination = "secrets/reflect-deltas.env"
        env         = true
        change_mode = "restart"
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
        cpu        = 5000
        memory     = 1536
        memory_max = 2560
      }
    }
  }
}
