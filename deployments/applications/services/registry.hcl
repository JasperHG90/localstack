job "registry" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "registry" {
    # The registry holds no local state -- every blob lives in the `registry`
    # MinIO bucket and there is no host volume -- so placement is purely a
    # capacity question. firebat, the obvious choice for being HAProxy's own
    # node, is committed to ~3100 MHz by Postgres and HAProxy and the
    # scheduler refused to place there. Colocating with MinIO buys nothing
    # either: every blob byte crosses the wire once regardless of which of
    # the two ends the registry sits on.
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    network {
      port "http" {
        static = 5000
      }
      # The debug listener serves /debug/health unauthenticated. The main
      # port cannot be health-checked: with htpasswd on, /v2/ answers 401
      # and Consul reads anything outside 2xx as critical.
      port "debug" {
        static = 5001
      }
    }

    task "registry" {
      driver = "podman"

      vault {}

      service {
        name = "registry"
        port = "http"
        tags = ["http", "registry"]

        check {
          name     = "registry health"
          type     = "http"
          port     = "debug"
          path     = "/debug/health"
          method   = "GET"
          interval = "15s"
          timeout  = "3s"
        }
      }

      config {
        image        = "docker.io/library/registry:3.1.1"
        args         = ["/secrets/config.yml"]
        ports        = ["http", "debug"]
        network_mode = "host"
      }

      # Config lives in secrets/ rather than local/ because it carries the
      # MinIO keys inline. The registry has no env-var expansion inside the
      # config file, so consul-template renders them in directly.
      template {
        data = <<-EOF
        version: 0.1
        log:
          level: info

        storage:
          s3:
            regionendpoint: http://192.168.2.29:9000
            # Required on v3 whenever regionendpoint is set.
            forcepathstyle: true
            # MinIO here is plain HTTP.
            secure: false
            # Required field; MinIO ignores the value.
            region: us-east-1
            bucket: registry
            {{- with secret "${registry_minio_secret}" }}
            accesskey: {{ .Data.data.access_key }}
            secretkey: {{ .Data.data.secret_key }}
            {{- end }}
          # Needed for `registry garbage-collect` to reclaim MinIO space;
          # deleting a tag alone never frees blobs.
          delete:
            enabled: true

        http:
          addr: 0.0.0.0:5000
          debug:
            addr: 0.0.0.0:5001

        auth:
          htpasswd:
            realm: localstack
            path: /secrets/htpasswd
        EOF

        destination = "secrets/config.yml"
        change_mode = "restart"
      }

      template {
        data = <<-EOF
        {{- with secret "${registry_auth_secret}" }}
        {{ .Data.data.htpasswd }}
        {{- end }}
        EOF

        destination = "secrets/htpasswd"
        change_mode = "restart"
      }

      # Deliberately small. The registry is I/O-bound -- it streams blobs to
      # MinIO rather than computing -- and ubuntu already carries the whole
      # observability stack (~3050 MHz and ~2.7 GB committed). A CPU
      # reservation is a scheduling commitment and a relative cgroup weight,
      # not a ceiling, so a low number still lets it use idle cycles.
      resources {
        cpu        = 100
        memory     = 256
        memory_max = 512
      }
    }
  }
}
