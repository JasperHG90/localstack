job "promtail" {
  datacenters = ["localstack"]
  type        = "system"
  namespace   = "default"

  group "promtail" {
    network {
      port "http" {
        static = 9080
      }
    }

    task "promtail" {
      driver = "podman"

      service {
        name = "promtail"
        port = "http"
        tags = ["monitoring"]

        check {
          name     = "promtail ready"
          type     = "http"
          port     = "http"
          path     = "/ready"
          method   = "GET"
          interval = "30s"
          timeout  = "3s"
        }
      }

      config {
        image = "docker.io/grafana/promtail:3.4.2"
        args = [
          "-config.file=/local/promtail.yml",
          "-config.expand-env=true",
        ]
        ports        = ["http"]
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
        server:
          http_listen_port: 9080
          grpc_listen_port: 0
          log_level: info

        positions:
          filename: /tmp/positions.yaml

        clients:
          - url: http://192.168.2.47:3100/loki/api/v1/push

        scrape_configs:
          - job_name: journal
            journal:
              max_age: 12h
              path: /run/log/journal
              labels:
                job: journald
                host: '{{ env "node.unique.name" }}'
            relabel_configs:
              - source_labels: ["__journal__systemd_unit"]
                target_label: unit
              - source_labels: ["__journal__hostname"]
                target_label: nodename
              - source_labels: ["__journal_priority_keyword"]
                target_label: level

          - job_name: nomad-alloc
            static_configs:
              - targets: [localhost]
                labels:
                  job: nomad
                  host: '{{ env "node.unique.name" }}'
                  __path__: /nomad/alloc/*/alloc/logs/*.std*.[0-9]*
            pipeline_stages:
              - regex:
                  source: filename
                  expression: '/nomad/alloc/(?P<alloc_id>[^/]+)/alloc/logs/(?P<task>[^.]+)\.(?P<stream>std(?:out|err))\.(?P<idx>\d+)'
              - labels:
                  alloc_id:
                  task:
                  stream:
        EOF

        destination = "local/promtail.yml"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
