job "wi-test" {
  datacenters = ["localstack"]
  type        = "service"

  group "probe" {
    count = 1

    task "probe" {
      driver = "podman"

      # Writes the WI JWT, the Vault token, and the rendered probe secret to
      # stdout so the operator verification can read them through `nomad
      # alloc logs` (the secret files under secrets/ are read-protected and
      # cannot be fetched with `nomad alloc fs`). Prints, then sleeps so the
      # alloc stays queryable.
      config {
        image   = "docker.io/library/alpine:3"
        command = "/bin/sh"
        args = ["-c", <<-SCRIPT
        echo '---JWT---'
        cat /secrets/nomad_vault_default.jwt
        echo
        echo '---PROBE-LEN---'
        wc -c < /secrets/probe.env
        echo '---PROBE---'
        cat /secrets/probe.env
        echo
        sleep 600
        SCRIPT
        ]
      }

      # Named identity: the load-bearing form. An unnamed `identity {}`
      # configures the task's default Nomad-API identity, not the Vault one,
      # so no JWT lands on disk and the keyless login leg is unexecutable.
      # `name = "vault_default"` matches the server-side `default_identity`
      # audience `vault.io`, and `file = true` writes the JWT to
      # `secrets/nomad_vault_default.jwt` inside the alloc.
      identity {
        name        = "vault_default"
        aud         = ["vault.io"]
        file        = true
        change_mode = "restart"
      }

      vault {}

      # Renders the probe secret the operator writes at
      # secret/data/default/wi-test/probe. A non-empty file proves the
      # keyless read succeeded end to end.
      template {
        data        = <<EOH
{{ with secret "secret/data/default/wi-test/probe" }}
PROBE_KEY={{ .Data.data.key }}
PROBE_NONCE={{ .Data.data.nonce }}
{{ end }}
EOH
        destination = "secrets/probe.env"
        env         = false
      }

      resources {
        cpu    = 100
        memory = 64
      }
    }
  }
}
