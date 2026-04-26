job "node-exporter" {
  datacenters = ["localstack"]
  type        = "system"
  namespace   = "default"

  group "node-exporter" {
    network {
      port "metrics" {
        static = 9100
      }
    }

    task "node-exporter" {
      driver = "podman"

      service {
        name = "node-exporter"
        port = "metrics"
        tags = ["monitoring"]

        check {
          name     = "node-exporter metrics"
          type     = "http"
          port     = "metrics"
          path     = "/metrics"
          method   = "GET"
          interval = "30s"
          timeout  = "3s"
        }
      }

      config {
        image = "docker.io/prom/node-exporter:v1.9.0"
        args = [
          "--path.procfs=/host/proc",
          "--path.sysfs=/host/sys",
          "--path.rootfs=/host/root",
          "--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)",
          "--no-collector.cpufreq",
          "--no-collector.hwmon",
          "--no-collector.thermal_zone",
          "--no-collector.edac",
          "--no-collector.powersupplyclass",
          "--web.listen-address=0.0.0.0:9100",
          "--web.max-requests=80",
        ]
        ports        = ["metrics"]
        network_mode = "host"
        volumes = [
          "/proc:/host/proc:ro",
          "/sys:/host/sys:ro",
          "/:/host/root:ro,rslave",
        ]
      }

      resources {
        cpu    = 200
        memory = 64
      }
    }
  }
}
