job "minio" {
  datacenters = ["localstack"]
  type        = "service"

  group "minio" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "orangepi4a"
    }

    volume "minio_data" {
      type            = "host"
      source          = "minio_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    network {
      port "http_api" {
        static = 9000
      }
      port "http_console" {
        static = 9001
      }
    }

    task "minio" {
      driver = "podman"

      vault {}

      ### The trailing `_NOMAD` names the OIDC target, and MinIO takes it
      ### VERBATIM: `getEnvVarName`/`GetAvailableTargets`
      ### (internal/config/config.go) case-fold nothing on the round trip, so
      ### an idiomatic uppercase env var yields the target `NOMAD`, never
      ### `nomad`. Anything referring to this provider by name must match.
      ###
      ### `config_url`, not `jwks_url`: RELEASE.2025-09-07 deleted the latter
      ### (openid.go's `LookupConfig` strips it as a deprecated key), so only
      ### a real discovery document works. F10 makes Nomad serve one.
      ###
      ### `client_id` must equal the `aud` in the consumer's identity block,
      ### because jwt.go's `Validate` checks the audience in EVERY mode, not
      ### just claim mode.
      ###
      ### `claim_name = nomad_job_id` is what makes access per-job. MinIO
      ### applies the policy NAMED BY that claim, and a Nomad WI JWT carries
      ### `nomad_job_id` as a fixed claim, so a `minio_iam_policy` whose name
      ### is the job id grants exactly that job and nothing else. There is no
      ### such policy in storage.tf today: M1 proved the mechanism with a
      ### throwaway one and removed it, so the first real consumer adds its
      ### own. docs/workload-identity.md ("Keyless MinIO access") is the
      ### procedure. `role_policy` cannot do this: it pins every workload
      ### assuming through the target to ONE policy, which is why M1 proved
      ### trust with it first and then moved off it.
      ###
      ### POC2 proves MinIO holds two IdPs at once, which the human-access
      ### sibling needs. Three rules govern it.
      ###
      ### It points at a REAL, reachable discovery document. `LookupConfig`
      ### aborts the WHOLE OIDC config load, every target, the moment any one
      ### document fails to parse, so a placeholder URL would take the working
      ### NOMAD target down with it.
      ###
      ### It carries a `role_policy` while NOMAD does not. A token with no
      ### RoleArn is resolved by claim mode, and `errSingleProvider`
      ### (openid.go) refuses a second claim-mode target, so exactly one
      ### target may sit in claim mode and every other one needs a policy.
      ###
      ### That policy NAME IS UNDEFINED ON PURPOSE, and it is the only reason
      ### this target is safe to leave standing. MinIO's sole principal check
      ### is `aud` matching `client_id`, and a jobspec author picks their own
      ### `aud`, so any real policy here would be a standing grant to anyone
      ### who types `aud = ["minio-poc2"]`. Naming a policy that does not
      ### exist costs nothing at startup (MinIO does not validate role-policy
      ### existence at config load) and fails the exchange per request, so
      ### the target proves the shape while granting exactly nothing. It
      ### previously named `memex_read_write`, which handed out s3:* on the
      ### memex bucket to anyone who asked; do not put a real policy back.
      ###
      ### The human-access ticket REPLACES this target rather than adding to
      ### it, or MinIO ends up with three.
      template {
        data        = <<-EOH
        MINIO_ROOT_USER="{{ with secret "${minio_secret}" }}{{ .Data.data.access_key }}{{ end }}"
        MINIO_ROOT_PASSWORD="{{ with secret "${minio_secret}" }}{{ .Data.data.secret_key }}{{ end }}"
        MINIO_PROMETHEUS_AUTH_TYPE="public"
        MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD="${nomad_oidc_config_url}"
        MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD="minio"
        MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"
        MINIO_IDENTITY_OPENID_CONFIG_URL_POC2="${nomad_oidc_config_url}"
        MINIO_IDENTITY_OPENID_CLIENT_ID_POC2="minio-poc2"
        MINIO_IDENTITY_OPENID_ROLE_POLICY_POC2="poc2-intentionally-undefined"
        EOH
        destination = "secrets/file.env"
        env         = true
      }

      service {
        name = "minio-console"
        port = "http_console"
        tags = ["http"]
      }

      service {
        name = "minio"
        port = "http_api"

        tags = ["http", "s3"]

        check {
          name     = "minio health check"
          type     = "http"
          port     = "http_api"
          path     = "/minio/health/live"
          method   = "GET"
          interval = "10s"
          timeout  = "5s"
        }
      }

      config {
        image   = "docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
        command = "server"
        args    = ["/data", "--console-address", ":9001"]
        ports   = ["http_api", "http_console"]
      }

      volume_mount {
        volume      = "minio_data"
        destination = "/data"
      }

      resources {
        cpu    = 5000
        memory = 2560
      }
    }
  }
}
