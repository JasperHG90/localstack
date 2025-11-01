job "docker_registry" {
  datacenters = ["localstack"]
  type        = "service"

  group "registry" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "localstack"
    }

    volume "docker_registry_data" {
      type            = "host"
      source          = "docker_registry_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    volume "docker_registry_auth" {
      type            = "host"
      source          = "docker_registry_auth"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    network {
      mode = "bridge"

      port "http_registry" {
        static = 5000
      }
      port "http_ui" {
        static = 5001
        to     = 80
      }
    }

    task "generate-htpasswd" {
      driver = "exec"

      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      vault {}

      template {
        data        = <<-EOH
        #!/bin/sh
        htpasswd -Bbc {{ env "NOMAD_ALLOC_DIR" }}/htpasswd '{{ with secret "${docker_registry_secret}" }}{{ .Data.data.username }}{{ end }}' '{{ with secret "${docker_registry_secret}" }}{{ .Data.data.password }}{{ end }}'
        mv {{ env "NOMAD_ALLOC_DIR" }}/htpasswd /auth/htpasswd
        EOH
        destination = "local/generate_htpasswd.sh"
        perms       = "0755"
      }

      config {
        command = "local/generate_htpasswd.sh"
      }

      volume_mount {
        volume      = "docker_registry_auth"
        destination = "/auth"
        read_only   = false
      }

      resources {
        cpu    = 100
        memory = 64
      }
    }

    task "registry" {
      driver = "podman"

      service {
        name = "docker-registry"
        port = "http_registry"
        tags = ["docker", "registry"]

        check {
          type     = "http"
          path     = "/"
          interval = "10s"
          timeout  = "2s"
          header {
            Authorization = ["Basic {{ with secret \"${docker_registry_secret}\" }}{{ printf \"%s:%s\" .Data.data.username .Data.data.password | base64Encode }}{{ end }}"]
          }
        }
      }

      config {
        image = "registry:3"
        ports = ["http_registry"]
      }

      env {
        REGISTRY_AUTH                   = "htpasswd"
        REGISTRY_AUTH_HTPASSWD_REALM    = "Registry Realm"
        REGISTRY_AUTH_HTPASSWD_PATH     = "/auth/htpasswd"
        REGISTRY_STORAGE_DELETE_ENABLED = "true"
      }

      resources {
        cpu    = 500
        memory = 256
      }

      volume_mount {
        volume      = "docker_registry_auth"
        destination = "/auth"
      }

      volume_mount {
        volume      = "docker_registry_data"
        destination = "/var/lib/registry"
      }
    }

    task "registry_ui" {
      driver = "podman"

      service {
        name = "docker-registry-ui"
        port = "http_ui"
        tags = ["docker", "registry", "ui"]

        check {
          type     = "http"
          path     = "/"
          interval = "10s"
          timeout  = "2s"
          header {
            Authorization = ["Basic {{ with secret \"${docker_registry_secret}\" }}{{ printf \"%s:%s\" .Data.data.username .Data.data.password | base64Encode }}{{ end }}"]
          }
        }
      }

      config {
        image = "docker.io/joxit/docker-registry-ui:main"
        ports = ["http_ui"]
      }

      env {
        SINGLE_REGISTRY      = "true"
        REGISTRY_TITLE       = "Localstack docker registry"
        NGINX_PROXY_PASS_URL = "http://$${attr.unique.network.ip-address}:5000"
        DELETE_IMAGES        = "true"
        SHOW_CONTENT_DIGEST  = "true"
      }

      resources {
        cpu    = 250
        memory = 128
      }
    }
  }
}
