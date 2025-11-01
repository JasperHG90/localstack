job "podman_config" {
  datacenters = ["localstack"]

  # The sysbatch type correctly runs this job once on all nodes.
  type = "sysbatch"

  group "config" {
    # By removing the lifecycle block, this is now a "main task".
    # Nomad will run it, wait for it to exit, and consider its work done.
    task "configure_insecure_registry" {
      driver = "raw_exec"

      config {
        command = "/bin/sh"
        args    = ["-c", "mkdir -p /etc/containers/registries.conf.d && cat local/insecure_registries.conf > /etc/containers/registries.conf.d/insecure_registries.conf"]
      }

      template {
        data        = <<-EOH
        [[registry]]
        location = "localstack.local:5000"
        insecure = true
        EOH
        destination = "local/insecure_registries.conf"
        change_mode = "noop"
        perms       = "0644"
      }

      user = "root"

      resources {
        cpu    = 100
        memory = 64
      }
    }

    # This is also a "main task". Nomad runs tasks in a group in parallel.
    task "podman_login" {
      driver = "raw_exec"

      vault {}

      config {
        command = "/bin/sh"
        args    = ["-c", "cat local/auth.json > /etc/containers/auth.json"]
      }

      template {
        data        = <<-EOH
        {{- with secret "${docker_registry_secret}" -}}
        {{- $auth := printf "%s:%s" .Data.data.username .Data.data.password | base64Encode -}}
        {
          "auths": {
            "localstack.local:5000": {
              "auth": "{{ $auth }}"
            }
          }
        }
        {{- end -}}
        EOH
        destination = "local/auth.json"
        change_mode = "noop"
        perms       = "0600"
      }

      user = "root"

      resources {
        cpu    = 100
        memory = 64
      }
    }
  }
}
