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

    ### Written out rather than inherited. With `check_restart` below, this is
    ### the whole automatic recovery path, and Nomad canonicalizes an omitted
    ### policy server-side, so a server-side default change would silently
    ### rewrite it.
    ###
    ### `interval` is sized off the slowest loop it has to bound, not off the
    ### restart rate. A task that keeps failing to boot cycles at `grace`
    ### (60m) plus `limit` x `interval` (2m) plus `delay`, so roughly 62m per
    ### restart. The 30m default counts restarts that cannot physically fit
    ### inside one boot; 2h fits only two, so `attempts = 3` would never
    ### exhaust and `mode = "fail"` would never fire. 4h holds three of them,
    ### which is what makes the handoff to the reschedule policy real rather
    ### than nominal.
    restart {
      attempts = 3
      interval = "4h"
      delay    = "30s"
      mode     = "fail"
    }

    ### Pinned for the same reason as `restart` above, and against the same
    ### measurement. Nomad's default `healthy_deadline` is 5m and an alloc is
    ### healthy only once both checks pass, so on the 44m46s boot a deployment
    ### would be marked failed while the task was still coming up correctly --
    ### an apply that looks broken and is not. No other job here needs this
    ### block; openviking is the only one whose boot outruns the default.
    update {
      healthy_deadline  = "60m"
      progress_deadline = "75m"
    }

    task "openviking" {
      driver = "podman"

      vault {}

      service {
        name    = "openviking"
        port    = "http"
        address = "${openviking_host}"

        tags = ["http", "context"]

        ### Liveness. /health answers out of the process itself: version, auth
        ### mode, and an identity resolve only when the caller sends a
        ### credential. It catches every exception on the way, so no backend
        ### can fail it.
        ###
        ### Measured, not read off upstream's router: `command` below starts
        ### ov_ext, so upstream's source answers for a different app than the
        ### one running. Unauthenticated GET /health on v0.4.17.1-9 returned
        ### 200 in 70ms:
        ### `{"status":"ok","healthy":true,"version":"v0.4.17.1","auth_mode":"oidc"}`
        ### Re-measure when the image moves.
        ###
        ### This is the ONLY check that may restart the task, and it can hold
        ### that power precisely because it reaches nothing. A wedged event
        ### loop or a dead process is the one failure a restart repairs, and
        ### it is the only failure this check reports.
        ###
        ### `grace` is sized off the worst measured boot, not off a round
        ### number. On alloc 6eff200c a clean boot bound port 1933 115s after
        ### the task started; the boot after a restart took 44m46s, because
        ### the ov-ext reflect sweep runs its LLM pass before the server binds
        ### and carries a backlog only after an unclean stop. The 60s that sat
        ### here killed at ~180s and turned one restart into a permanent loop.
        ### 60m clears the measured worst boot with room; shorten it only
        ### after the sweep stops blocking the bind.
        check {
          name     = "openviking alive"
          type     = "http"
          port     = "http"
          path     = "/health"
          method   = "GET"
          interval = "30s"
          timeout  = "5s"

          check_restart {
            limit = 4
            grace = "60m"
          }
        }

        ### Readiness, and deliberately NO check_restart. /ready dials three
        ### other machines on every pass: MinIO for the AGFS ls, Postgres for
        ### the vector store, and Bifrost on to embark for a live one-token
        ### embedding. Any one of them down answers 503.
        ###
        ### A check_restart here killed a healthy server: every restart logged
        ### `Restart Signaled: check "openviking ready" unhealthy` followed by
        ### `Exit Code: 0`, with every dependency still registered in Consul.
        ###
        ### The stall is inside this process, not at any of those three hosts.
        ### Bifrost meters the embedder it fronts at ~100ms mean and 250ms p99
        ### while OpenViking logs the same calls at `wait_ms` up to 30430 and
        ### `duration_ms` in seconds, and a Postgres task-store update logged
        ### 8322ms over the same window. One process stalling every backend at
        ### once is a blocked event loop. Cycling the task clears none of that
        ### and fails /ready again on the way back up.
        ###
        ### It is NOT the CPU quota, which was the first guess and is wrong.
        ### Read off the radxa client agent's own metrics for this alloc:
        ### `nomad_client_allocs_cpu_throttled_periods` and `..._throttled_time`
        ### are both 0 -- cumulative since the alloc started, so the cgroup has
        ### never once throttled it -- against 706 of the 5000 MHz in
        ### `resources` below. Raising `cpu` buys nothing. A loop that stalls
        ### while burning no CPU is blocked on something synchronous inside a
        ### handler, not starved of cycles.
        ###
        ### A single search was measured fanning out to 30-37 embedding calls.
        ### Where that fan-out is built is NOT established: it is not
        ### `prefetch_search_topn` x `OV_RETRIEVAL_POOL_FACTOR`, which an
        ### earlier draft of this comment asserted. Upstream embeds the query
        ### once (hierarchical_retriever.py), `prefetch_search_topn` slices
        ### AGFS reads rather than embeddings, and the search that drives the
        ### retriever runs whether or not `eager_prefetch` is set. The
        ### multiplier lives in ov_ext's patched HierarchicalRetriever, which
        ### is not vendored here. Read it at the pinned tag before tuning
        ### either number.
        ###
        ### The cost is that a server which starts but never readies is now
        ### left running and marked critical rather than cycled. That is the
        ### better half of the trade: what never readies is a broken image or a
        ### downed backend, and a restart repairs neither.
        ###
        ### 15s, not 5s. `asyncio.wait_for` grants the embedding probe alone
        ### 10s inside the handler, and the AGFS and vectordb round trips run
        ### before it, so a 5s timeout expired while OpenViking was still
        ### deciding. A check has to outlast what it measures.
        ###
        ### Nothing routes on this. HAProxy's ovapi backend is a static server
        ### line carrying its own check, so the check reaches the Consul
        ### catalog and `localstack service` and stops there. The Grafana
        ### readiness panels read OpenViking's own /metrics and never see it.
        ###
        ### Which means dropping check_restart dropped the only automatic
        ### answer to a stuck /ready. OpenVikingNotReady in
        ### grafana/alert-rules.yaml replaces it, and covers only this case: a
        ### reachable OpenViking with a sick backend. A dead or wedged process
        ### reads as no data there, so OpenVikingDown (`up == 0`) beside it
        ### covers that half, and the `openviking alive` check above restarts
        ### it. ScrapeJobMissing catches neither: it fires when the scrape
        ### block is deleted, not when the target it names is down.
        ###
        ### 60s, not 30s. Each pass costs a live one-token embedding through
        ### Bifrost, an S3 ls against MinIO, and a Postgres query, on the one
        ### CPU that is already the bottleneck. Halving the rate halves that
        ### self-inflicted load and delays nothing: no restart hangs off this
        ### check, and OpenVikingNotReady waits 10m before it fires.
        check {
          name     = "openviking ready"
          type     = "http"
          port     = "http"
          path     = "/ready"
          method   = "GET"
          interval = "60s"
          timeout  = "15s"
        }
      }

      ### `command` and `args` land as the container command, so the image's
      ### `openviking-entrypoint` receives them and `exec`s them on its first
      ### non-bot argument. Three things it would have done are given up with
      ### that exec: writing the config, which the template below already did;
      ### polling /health for 120s and failing the task if the server never
      ### bound, which nothing replaces: `check_restart` below is a
      ### steady-state wedge detector and its `grace = 60m` is chosen so that
      ### nothing acts during boot. A server that never binds is now caught by
      ### OpenVikingDown in grafana/alert-rules.yaml, by paging a human; and
      ### honoring
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
        OV_REFLECT_MODEL            = "ollama/deepseek-v4.1-flash"
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

      ### No `memory_max`. Oversubscription is off at the Nomad server, so the
      ### scheduler zeroes MemoryMaxMB and the client builds the cgroup from
      ### `memory` alone. embark.hcl carries the same finding, measured there
      ### through podman inspect rather than inferred. The `memory_max = 2560`
      ### that sat here read as 1024 MB of headroom the kernel never granted:
      ### 1536 was always the enforced cap, so dropping the line changes
      ### nothing at steady state. The apply is not free: Nomad reads a
      ### task-resources diff as a destructive update and replaces the alloc.
      resources {
        cpu    = 5000
        memory = 1536
      }
    }
  }
}
