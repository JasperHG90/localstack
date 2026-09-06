### oauth2-proxy: OIDC forward-gate for OpenViking. A copy of
### oauth2-proxy-registry-ui.hcl, which says this pattern is meant to be
### copied: against Vault's `lab` provider. Flat access: any authenticated
### user is let through (OAUTH2_PROXY_EMAIL_DOMAINS=*, and the Vault client is
### bound to the built-in "allow_all" assignment in oidc.tf).
###
### This proxy is a NETWORK GATE. OpenViking runs `auth_mode: "api_key"` and
### resolves each caller from their own key, so the proxy's job is only to keep
### the hostname behind a Vault login.
###
### It does still inject four headers, because PASS_USER_HEADERS defaults TRUE
### in v7 and is not set below: X-Forwarded-Groups, -User, -Email and
### -Preferred-Username. OpenViking reads none of them -- `_extract_api_key`
### accepts only X-API-Key and `Authorization: Bearer`, and the api_key plugin
### strips X-OpenViking-User itself -- so they are inert rather than a second
### identity.
###
### It injects NO Authorization header, and touches an incoming one not at all.
### Read from v7.13.0's source rather than its flag table, because the table
### reads the other way: legacy_options.go:237 gates the Basic header on
### `BasicAuthPassword != ""`, which nothing here sets, and :256 builds the
### SKIP_AUTH_STRIP_HEADERS strip list out of the INJECTED headers only. So a
### caller through the edge may present its key as X-API-Key or as
### `Authorization: Bearer`; Studio uses the former.
###
### COOKIE_EXPIRE matches the client's 3600s id_token_ttl. The default is
### 168h, which would leave a session valid for a week after the token behind
### it expired.
###
### Seven settings decide whether this job works at all, and each one passes
### `nomad fmt`/`terraform validate` while being wrong: EMAIL_DOMAINS and
### UPSTREAMS are PLURAL in env form though their flags are singular
### (--email-domain, --upstream); OIDC_EMAIL_CLAIM is `sub` because THIS job
### requests only `openid`, so its token carries no `email` claim. PROVIDER
### must be `oidc` (default is `google`); HTTP_ADDRESS must bind 0.0.0.0, not
### the 4180 loopback default; SKIP_PROVIDER_BUTTON is pinned `false`; and the
### health check below must probe /ping, never /.
###
### OAUTH2_PROXY_REVERSE_PROXY is deliberately unset (defaults false): HAProxy
### sends no X-Forwarded-Proto/-Host, so the redirect URL is given explicitly
### below instead of trusting headers nobody sends.
job "oauth2-proxy-openviking" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "oauth2-proxy-openviking" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    network {
      port "http" {
        static = 4182
      }
    }

    task "oauth2-proxy" {
      driver = "podman"

      vault {}

      ### One catch-all upstream: OpenViking serves its API and its Studio UI
      ### from the same port, so there is no split to path-scope.
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
        OAUTH2_PROXY_UPSTREAMS="${upstream}"
        OAUTH2_PROXY_OIDC_EMAIL_CLAIM="sub"
        OAUTH2_PROXY_SCOPE="openid"
        OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="false"
        OAUTH2_PROXY_HTTP_ADDRESS="0.0.0.0:4182"
        OAUTH2_PROXY_COOKIE_EXPIRE="3600s"
        EOH
        destination = "secrets/file.env"
        env         = true
      }

      service {
        name = "oauth2-proxy-openviking"
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
