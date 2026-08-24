### oauth2-proxy: OIDC forward-gate for the cluster landing page (dash),
### against Vault's `lab` provider. Flat access: any authenticated user is
### let through (OAUTH2_PROXY_EMAIL_DOMAINS=*, and the Vault client is bound
### to the built-in "allow_all" assignment in oidc.tf).
###
### Reusable pattern: R1 (MLflow) and R4 (Phoenix) copy this job. Keep
### host/redirect/issuer values as template vars so it stays copyable without
### editing the job body.
###
### Seven settings decide whether this job works at all, and each one passes
### `nomad fmt`/`terraform validate` while being wrong: EMAIL_DOMAINS and
### UPSTREAMS are PLURAL in env form though their flags are singular
### (--email-domain, --upstream); OIDC_EMAIL_CLAIM must be `sub` because
### Vault's ID token carries no `email` claim; PROVIDER must be `oidc`
### (default is `google`); HTTP_ADDRESS must bind 0.0.0.0, not the 4180
### loopback default; SKIP_PROVIDER_BUTTON is pinned `false`; and the health
### check below must probe /ping, never /.
###
### OAUTH2_PROXY_REVERSE_PROXY is deliberately unset (defaults false): HAProxy
### sends no X-Forwarded-Proto/-Host, so the redirect URL is given explicitly
### below instead of trusting headers nobody sends.
job "oauth2-proxy" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "oauth2-proxy" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    network {
      port "http" {
        static = 4180
      }
    }

    task "oauth2-proxy" {
      driver = "podman"

      vault {}

      ### OAUTH2_PROXY_UPSTREAMS below carries two upstreams for dash's
      ### frontend/backend split (L4): a catch-all to the frontend's
      ### loopback port, and a path-scoped one to the backend's
      ### `/api/status`. Verified against a real oauth2-proxy v7.13.0
      ### container (L4 implementation, 2026-08-24): the path-scoped
      ### upstream matches the given path EXACTLY, not as a prefix (`GET
      ### /api/status` routes to the backend; `GET /api/status/nested`
      ### falls through to the catch-all, logged as matching mapping key
      ### "/"). `index.html`'s one fetch call is an exact, unparameterized
      ### `/api/status`, so exact-match is exactly what this needs --
      ### resolves P10's prefix-vs-exact uncertainty from the planning
      ### pass.
      template {
        data        = <<-EOH
        OAUTH2_PROXY_PROVIDER="oidc"
        OAUTH2_PROXY_OIDC_ISSUER_URL="{{ with secret "${oidc_secret}" }}{{ .Data.data.issuer }}{{ end }}"
        OAUTH2_PROXY_CLIENT_ID="{{ with secret "${oidc_secret}" }}{{ .Data.data.client_id }}{{ end }}"
        OAUTH2_PROXY_CLIENT_SECRET="{{ with secret "${oidc_secret}" }}{{ .Data.data.client_secret }}{{ end }}"
        OAUTH2_PROXY_COOKIE_SECRET="{{ with secret "${cookie_secret}" }}{{ .Data.data.secret }}{{ end }}"
        OAUTH2_PROXY_COOKIE_SECURE="true"
        OAUTH2_PROXY_REDIRECT_URL="${redirect_url}"
        OAUTH2_PROXY_EMAIL_DOMAINS="*"
        OAUTH2_PROXY_UPSTREAMS="${dash_frontend_upstream},${dash_backend_upstream}"
        OAUTH2_PROXY_OIDC_EMAIL_CLAIM="sub"
        OAUTH2_PROXY_SCOPE="openid"
        OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="false"
        OAUTH2_PROXY_HTTP_ADDRESS="0.0.0.0:4180"
        EOH
        destination = "secrets/file.env"
        env         = true
      }

      service {
        name = "oauth2-proxy"
        port = "http"
        tags = ["http", "auth", "oidc"]

        check {
          name     = "oauth2-proxy ping"
          type     = "http"
          port     = "http"
          path     = "/ping"
          method   = "GET"
          interval = "10s"
          timeout  = "3s"
        }
      }

      config {
        image        = "quay.io/oauth2-proxy/oauth2-proxy:v7.13.0"
        ports        = ["http"]
        network_mode = "host"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
