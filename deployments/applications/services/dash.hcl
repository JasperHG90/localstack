job "dash" {
  datacenters = ["localstack"]
  type        = "service"

  group "dash" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    network {
      port "http" {
        static = 8000
      }
    }

    task "dash" {
      driver = "podman"

      service {
        name = "dash"
        port = "http"

        check {
          type     = "http"
          path     = "/api/status"
          interval = "30s"
          timeout  = "5s"
        }
      }

      config {
        image        = "ghcr.io/jasperhg90/dash:${dash_version}"
        network_mode = "host"
        volumes = [
          "local/tiles.json:/local/tiles.json",
        ]
      }

      env {
        NOMAD_ADDR       = "${nomad_addr}"
        CONSUL_HTTP_ADDR = "${consul_addr}"
        NOMAD_TOKEN_FILE = "secrets/nomad-token"
        DASH_TILES_PATH  = "/local/tiles.json"
        PORT             = "8000"
      }

      ### The dash-read Nomad token, minted by Vault's nomad secrets engine
      ### (nomad_dash_read_role.tf) exactly like a database secrets-engine
      ### credential is minted -- the same `{{ with secret "<path>" }}`
      ### template syntax, just against the nomad backend instead of
      ### database. Read-only: read-job, list-jobs, node:read. No
      ### submit-job, no host-volume-*, no management capability.
      vault {
        role = "dash"
      }

      ### Single-nested `.Data.secret_id`, NOT `.Data.data.secret_id`. The
      ### double `data.data` nesting elsewhere in this repo (postgres.hcl,
      ### redis.hcl, bifrost.hcl) is a KV2-specific artifact -- KV2 wraps
      ### its payload in an extra `data` key to carry versioning, which no
      ### other secrets engine does. `vault read nomad/creds/deploy`
      ### returns `secret_id` one level under `data`, confirmed against
      ### this repo's own working code: cli/src/localstack_cli/auth/broker.py
      ### reads it as `response["data"]["secret_id"]` (found in adversarial
      ### review, AR2).
      template {
        data        = <<-EOH
        {{ with secret "nomad/creds/dash_read" }}{{ .Data.secret_id }}{{ end }}
        EOH
        destination = "secrets/nomad-token"
      }

      ### The tile list. A plain JSON file (tiles.json), round-tripped
      ### through jsondecode/jsonencode on the Terraform side
      ### (services.tf) so a syntax error fails `terraform plan`, not this
      ### job -- same pattern memex's auth_keys.json/auth_oidc.json use
      ### (services.tf's own comment on that local).
      template {
        data        = "${tiles_json}"
        destination = "local/tiles.json"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
