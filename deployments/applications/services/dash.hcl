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
      port "backend" {
        static = 8001
      }
    }

    task "frontend" {
      driver = "podman"

      service {
        name = "dash-frontend"
        port = "http"

        check {
          type     = "http"
          path     = "/"
          interval = "30s"
          timeout  = "5s"
        }
      }

      config {
        image        = "ghcr.io/jasperhg90/dash-frontend:${dash_frontend_version}"
        network_mode = "host"
      }

      resources {
        cpu    = 50
        memory = 32
      }
    }

    task "backend" {
      driver = "podman"

      service {
        name = "dash-backend"
        port = "backend"

        check {
          type     = "http"
          path     = "/api/status"
          interval = "30s"
          timeout  = "5s"
        }
      }

      config {
        image        = "ghcr.io/jasperhg90/dash-backend:${dash_backend_version}"
        network_mode = "host"
        volumes = [
          "local/tiles.json:/local/tiles.json",
        ]
      }

      env {
        NOMAD_ADDR       = "${nomad_addr}"
        CONSUL_HTTP_ADDR = "${consul_addr}"
        NOMAD_TOKEN_FILE = "/secrets/nomad-token"
        DASH_TILES_PATH  = "/local/tiles.json"
        PORT             = "8001"
      }

      ### The dash-read Nomad token, minted by Vault's nomad secrets engine
      ### (nomad_dash_read_role.tf) exactly like a database secrets-engine
      ### credential is minted -- the same `{{ with secret "<path>" }}`
      ### template syntax, just against the nomad backend instead of
      ### database. Read-only: read-job, list-jobs, node:read. No
      ### submit-job, no host-volume-*, no management capability.
      ###
      ### This stanza lives on the backend task only, not the frontend
      ### (L4: the frontend serves static files alone and needs no
      ### credential at all). nomad_dash_read_role.tf's bound_claims check
      ### the job id, not the task name, so moving this stanza between
      ### tasks in the same job needs no Terraform change.
      vault {
        role = "dash"
      }

      ### Single-nested `.Data.secret_id`, NOT `.Data.data.secret_id`. The
      ### double `data.data` nesting elsewhere in this repo (postgres.hcl,
      ### redis.hcl, bifrost.hcl) is a KV2-specific artifact -- KV2 wraps
      ### its payload in an extra `data` key to carry versioning, which no
      ### other secrets engine does. `vault read nomad/creds/deploy`
      ### returns `secret_id` one level under `data`, confirmed against
      ### this repo's own working code (originally cli/src/localstack_cli/
      ### auth/broker.py, which reads it as `response["data"]["secret_id"]`;
      ### found in adversarial review, AR2, under L3).
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
      ### A heredoc, not a quoted string: tiles_json is raw JSON text
      ### (jsonencode output), which carries embedded double quotes.
      ### Splicing that into a plain quoted data string breaks Nomad's own
      ### jobspec parser the moment the first embedded quote closes the
      ### HCL string early -- caught only at terraform apply (the nomad
      ### provider's jobspec parse step), since neither terraform validate
      ### nor nomad fmt parse the rendered jobspec, only the template
      ### source. A heredoc needs no quote-escaping, and tiles.json
      ### contains no dollar-sign characters (confirmed by grep), so
      ### Nomad's own interpolation syntax cannot misfire on the
      ### substituted content.
      template {
        data        = <<-EOH
        ${tiles_json}
        EOH
        destination = "local/tiles.json"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
