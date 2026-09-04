job "alloy" {
  datacenters = ["localstack"]
  type        = "system"
  namespace   = "default"

  group "alloy" {
    network {
      port "http" {
        static = 12345
      }

      # OTLP ingest, NOT on 4317/4318. Those are taken on two nodes already --
      # tempo binds them on rpi5 and phoenix on orangepi4a -- and this is a
      # system job, so claiming them would fail placement on exactly those two
      # nodes and silently stop shipping their logs. Declared static so Nomad
      # keeps enforcing that, rather than leaving two jobs to race for a bind.
      port "otlp_grpc" {
        static = 4319
      }

      port "otlp_http" {
        static = 4320
      }
    }

    task "alloy" {
      driver = "podman"

      service {
        name = "alloy"
        port = "http"
        tags = ["monitoring"]

        check {
          name     = "alloy ready"
          type     = "http"
          port     = "http"
          path     = "/-/ready"
          method   = "GET"
          interval = "30s"
          timeout  = "3s"
        }
      }

      config {
        image = "docker.io/grafana/alloy:v1.19.2"
        args = [
          "run",
          "--server.http.listen-addr=0.0.0.0:12345",
          # Positions live in the alloc dir, so a task restart resumes where it
          # stopped instead of re-shipping every file from the top.
          "--storage.path=/alloc/data/alloy",
          "--disable-reporting",
          "/local/config.alloy",
        ]
        ports        = ["http", "otlp_grpc", "otlp_http"]
        network_mode = "host"
        volumes = [
          "/var/log:/var/log:ro",
          "/run/log/journal:/run/log/journal:ro",
          "/etc/machine-id:/etc/machine-id:ro",
          "/opt/nomad/data/alloc:/nomad/alloc:ro,rslave",
        ]
      }

      template {
        data = <<-EOF
        logging {
          level  = "info"
          format = "logfmt"
        }

        loki.write "default" {
          endpoint {
            url = "http://192.168.2.47:3100/loki/api/v1/push"
          }
        }

        // ---- journald ----
        // forward_to is empty on purpose: this component exists only to
        // export `rules`, which loki.source.journal consumes.
        loki.relabel "journal" {
          forward_to = []

          rule {
            source_labels = ["__journal__systemd_unit"]
            target_label  = "unit"
          }

          rule {
            source_labels = ["__journal__hostname"]
            target_label  = "nodename"
          }

          rule {
            source_labels = ["__journal_priority_keyword"]
            target_label  = "level"
          }
        }

        loki.source.journal "journal" {
          path          = "/run/log/journal"
          max_age       = "12h"
          relabel_rules = loki.relabel.journal.rules
          labels = {
            job  = "journald",
            host = "{{ env "node.unique.name" }}",
          }
          forward_to = [loki.write.default.receiver]
        }

        // ---- Nomad task logs ----
        local.file_match "nomad_alloc" {
          path_targets = [{
            __path__ = "/nomad/alloc/*/alloc/logs/*.std*.[0-9]*",
            job      = "nomad",
            host     = "{{ env "node.unique.name" }}",
          }]
        }

        // Promtail pulled alloc_id/task/stream out of the filename with
        // pipeline_stages. Alloy has no `filename` source for stage.regex, so
        // the same three labels come off __path__ at discovery time instead.
        // Relabel regexes are fully anchored, so each rule spells out the whole
        // path and captures one field.
        discovery.relabel "nomad_alloc" {
          targets = local.file_match.nomad_alloc.targets

          rule {
            source_labels = ["__path__"]
            regex         = "/nomad/alloc/([^/]+)/alloc/logs/[^.]+\\.std(?:out|err)\\.[0-9]+"
            target_label  = "alloc_id"
            replacement   = "$1"
          }

          rule {
            source_labels = ["__path__"]
            regex         = "/nomad/alloc/[^/]+/alloc/logs/([^.]+)\\.std(?:out|err)\\.[0-9]+"
            target_label  = "task"
            replacement   = "$1"
          }

          rule {
            source_labels = ["__path__"]
            regex         = "/nomad/alloc/[^/]+/alloc/logs/[^.]+\\.(std(?:out|err))\\.[0-9]+"
            target_label  = "stream"
            replacement   = "$1"
          }
        }

        loki.source.file "nomad_alloc" {
          targets    = discovery.relabel.nomad_alloc.output
          forward_to = [loki.write.default.receiver]
        }

        // ---- OTLP traces ----
        // Bound to loopback on purpose. A workload traces to 127.0.0.1 and
        // never learns where Tempo lives, so moving or replacing the trace
        // backend is a change here rather than a redeploy of every producer.
        // Loopback also means no firewall rule: nothing off-node can reach it.
        otelcol.receiver.otlp "default" {
          grpc {
            endpoint = "127.0.0.1:4319"
          }

          http {
            endpoint = "127.0.0.1:4320"
          }

          output {
            traces = [otelcol.processor.batch.default.input]
          }
        }

        otelcol.processor.batch "default" {
          output {
            traces = [otelcol.exporter.otlp.tempo.input]
          }
        }

        otelcol.exporter.otlp "tempo" {
          client {
            endpoint = "192.168.2.47:4317"

            // Tempo's OTLP listener is plaintext gRPC on the LAN, the same
            // shape as the Loki push above.
            tls {
              insecure = true
            }
          }
        }
        EOF

        destination = "local/config.alloy"
      }

      # 128 MB reserved, matching what Promtail ran on for the same two log
      # sources: this is a system job, so the reservation has to fit the
      # tightest node. orangepi4a carries MinIO and Phoenix and has no room
      # for 256, and a system job that cannot place there silently stops
      # shipping that node's logs. memory_max lets Alloy use more where a
      # node has slack.
      resources {
        cpu        = 200
        memory     = 128
        memory_max = 256
      }
    }
  }
}
