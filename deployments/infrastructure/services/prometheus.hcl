job "prometheus" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "prometheus" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    network {
      port "http" {
        static = 9090
      }
    }

    volume "prometheus_data" {
      type            = "host"
      source          = "prometheus_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    task "prometheus" {
      driver = "podman"
      user   = "root"

      service {
        name = "prometheus"
        port = "http"
        tags = ["http", "monitoring"]

        check {
          name     = "prometheus ready"
          type     = "http"
          port     = "http"
          path     = "/-/ready"
          method   = "GET"
          interval = "10s"
          timeout  = "3s"
        }
      }

      config {
        image = "docker.io/prom/prometheus:v3.2.1"
        args = [
          "--config.file=/local/prometheus.yml",
          "--storage.tsdb.path=/prometheus",
          "--storage.tsdb.retention.time=30d",
          "--web.enable-lifecycle",
          "--web.enable-admin-api",
        ]
        ports        = ["http"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "prometheus_data"
        destination = "/prometheus"
      }

      template {
        data = <<-EOF
        global:
          scrape_interval:     30s
          evaluation_interval: 30s
          external_labels:
            cluster: localstack

        scrape_configs:
          - job_name: prometheus
            static_configs:
              - targets: ["192.168.2.47:9090"]

          - job_name: nomad
            metrics_path: /v1/metrics
            params:
              format: ["prometheus"]
            static_configs:
              - targets: ["192.168.2.30:4646"]

          - job_name: consul
            metrics_path: /v1/agent/metrics
            params:
              format: ["prometheus"]
            static_configs:
              - targets: ["192.168.2.30:8500"]

          - job_name: haproxy
            static_configs:
              - targets: ["192.168.2.30:8404"]

          - job_name: postgres
            static_configs:
              - targets: ["192.168.2.30:9187"]

          - job_name: minio
            metrics_path: /minio/v2/metrics/cluster
            static_configs:
              - targets: ["192.168.2.29:9000"]

          # memex omitted: /metrics requires auth — wire up via Consul SD when
          # an auth-aware Prometheus config is added (or remove the auth gate).

          # Per-node node-exporter targets (system job, one per host).
          # Relabel rewrites `instance` from "<ip>:9100" → "<hostname>" so
          # series are identified by hostname everywhere.
          - job_name: node
            static_configs:
              - targets: ["192.168.2.30:9100"]
                labels: {node: firebat}
              - targets: ["192.168.2.29:9100"]
                labels: {node: orangepi4a}
              - targets: ["192.168.2.46:9100"]
                labels: {node: jetson-orin-nano}
              - targets: ["192.168.2.47:9100"]
                labels: {node: ubuntu}
              - targets: ["192.168.2.50:9100"]
                labels: {node: radxa-dragon-q6a}
            relabel_configs:
              - source_labels: [node]
                target_label: instance

          # Auto-discover any service tagged "prometheus" in Consul
          - job_name: consul_services
            consul_sd_configs:
              - server: "${consul_address}"
            relabel_configs:
              - source_labels: [__meta_consul_tags]
                regex: ".*,prometheus,.*"
                action: keep
              - source_labels: [__meta_consul_service]
                target_label: job
              - source_labels: [__meta_consul_node]
                target_label: instance
              - source_labels: [__meta_consul_service_metadata_metrics_path]
                regex: "(.+)"
                target_label: __metrics_path__
        EOF

        destination   = "local/prometheus.yml"
        change_mode   = "signal"
        change_signal = "SIGHUP"
      }

      resources {
        cpu    = 1000
        memory = 1024
      }
    }
  }
}
