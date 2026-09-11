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

      ### GOMEMLIMIT is the one that stops the OOM. Go's GC targets a heap size
      ### and knows nothing about the cgroup cap, so it grows past 768 MB and the
      ### kernel kills it. The task dies on SIGKILL (exit 137), which reads as a
      ### crash rather than a limit being hit. The soft limit makes the GC run
      ### harder as it approaches, trading CPU for memory. Set below the cap, not
      ### at it: GOMEMLIMIT covers the Go heap, while the cgroup also counts
      ### goroutine stacks, page cache for block reads, and the runtime itself.
      ###
      ### AWS_WEB_IDENTITY_TOKEN_FILE and TEST_IAM_ENDPOINT send tempo down
      ### minio-go's web-identity path.
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
        GOMEMLIMIT                  = "600MiB"
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

        # Cut from 30m, and this is a memory knob rather than a flush cadence.
        # Every time the head block is cut, `walBlock.Flush` hands its trace-ID
        # map to the flushed list (tempodb/encoding/vparquet4/wal_block.go) and
        # those maps stay resident for as long as the block does, so a 5m block
        # holds roughly a sixth of what a 30m one did.
        #
        # `max_block_bytes` is deliberately NOT set alongside it. It reads like
        # a memory bound and is not one: it is compared against
        # `walBlock.DataLength()`, whose own comment calls it the estimated size
        # of the WAL files ON DISK.
        ingester:
          max_block_duration: 5m

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

        # The generator runs ONLY the local-blocks processor, which keeps
        # recent spans queryable so Grafana can run TraceQL metrics over them.
        # No span-metrics, no service-graphs, and so no remote_write and no
        # Prometheus change: nothing here writes a time series. What it buys is
        # the one thing span-metrics cannot do, aggregating a span ATTRIBUTE's
        # value -- `avg_over_time(span.ov_retrieval.keyword_hits)` -- which is
        # why ov-retrieval's spans are worth having.
        #
        # `storage.path` is NOT optional despite nothing being remote-written.
        # Without it Tempo logs "metrics-generator is not configured ... will be
        # disabled" at info level and starts anyway, so every TraceQL metrics
        # query returns empty with no error. Verified by running this exact
        # config under grafana/tempo:2.10.8: the warning is present without the
        # key and the metrics-generator module starts with it.
        #
        # `max_live_traces` is the ONLY bound on the generator's live-trace map
        # on this deployment, which is why it is worth a paragraph.
        #
        # `max_live_traces_bytes` looks like the better knob, since a byte cap
        # bounds memory directly and a trace count only proxies it. It is unset
        # because it cannot run here: it is read only inside
        # `Processor.backpressure`, which only `DeterministicPush` calls, which
        # only runs on the queue-based processor, which exists only when
        # `traces_query_storage` is set. The live path is `PushSpans`, which
        # calls `push` with no backpressure at all. Setting that key to reach it
        # would add a second per-tenant WAL and a second processor instance --
        # more memory to bound memory, on the node with the least of it.
        #
        # So the count cap is the bound, and exceeding it DROPS traces. Not
        # silently: watch
        # `tempo_metrics_generator_processor_local_blocks_traces_dropped_total`
        # with `reason="live_traces_exceeded"`, alerted as TempoTracesDropped.
        #
        # `complete_block_timeout` is also unset, deliberately. It is not just
        # retention: `GetMetrics` rejects any query window older than it, so
        # shortening it to save memory silently shortens how far back a TraceQL
        # metrics query can reach.
        #
        # NOT set: `filter_server_spans`. Its name suggests it drops the
        # INTERNAL spans ov_postgres and ov_retrieval emit, which would make
        # this whole block pointless. Tested at the default of true against
        # 2.10.8 by pushing one internal and one server span: both were
        # counted and `avg_over_time` over an internal span's attribute
        # returned its value. It does not need changing.
        metrics_generator:
          processor:
            local_blocks:
              flush_to_storage: true
              max_live_traces: 5000
          traces_storage:
            path: /var/tempo/generator/traces
          storage:
            path: /var/tempo/generator/wal

        # Processors are enabled per tenant, never in the block above.
        overrides:
          defaults:
            metrics_generator:
              processors: [local-blocks]

        usage_report:
          reporting_enabled: false
        EOF

        destination = "local/tempo-config.yaml"
      }

      # 768 is a ceiling this task fits inside, not headroom to grow into. Do
      # not raise it to fix an OOM: this node is a Pi 4B already carrying
      # Prometheus, Loki, Grafana and Alloy, so there is nothing to raise it
      # with. GOMEMLIMIT is what holds it under, and it is enough -- on
      # 2026-09-11 it settled at ~266 MiB replaying the same WAL the unbounded
      # config had been dying on every 18 seconds.
      #
      # If it OOMs again, lower GOMEMLIMIT first. The next real knob is
      # `parquet_row_group_size_bytes`, which defaults to ~95 MiB per writer
      # and the ingester and generator each run one. This number is last.
      resources {
        cpu    = 500
        memory = 768
      }
    }
  }
}
