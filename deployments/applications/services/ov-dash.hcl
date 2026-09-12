### ov-dash: the browser face of OpenViking, on orangepi4a.
###
### Not colocated with OpenViking, which is the one thing this job would
### otherwise want. radxa had 598 MB free and its two stateful neighbours are
### pinned there -- driftwatch's baseline volume and OpenViking's own workspace
### are both single-node-writer host volumes constrained to that host, so
### neither can move to make room. This job holds nothing on disk, so it is the
### one that moves. The cost is a LAN hop to 1933 instead of loopback, which is
### noise against a `search/grep` that takes twenty seconds per term.
###
### ONE alloc, deliberately. Sessions live in this process's memory, so a
### second replica would sign a person out whenever HAProxy sent them to the
### other one. Scaling out needs a shared session store, not a higher count.
### A restart signs everybody out; that is the accepted price of holding no
### database.
job "ov-dash" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "ov-dash" {
    count = 1

    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${ov_dash_hostname}"
    }

    network {
      port "http" {
        static = 4182
      }
    }

    task "ov-dash" {
      driver = "podman"

      vault {}

      service {
        name    = "ov-dash"
        port    = "http"
        address = "${ov_dash_host}"

        tags = ["http", "openviking"]

        ### /health, the same endpoint the image's own HEALTHCHECK probes. It
        ### answers before any credential exists, so it reports the process
        ### rather than whether Vault or OpenViking are reachable -- a sign-in
        ### failure is not a reason to restart this task.
        check {
          name     = "ov-dash alive"
          type     = "http"
          port     = "http"
          path     = "/health"
          method   = "GET"
          interval = "30s"
          timeout  = "5s"
        }
      }

      config {
        image        = "${ov_dash_image}"
        ports        = ["http"]
        network_mode = "host"
      }

      ### OV_URL is the in-cluster address, NOT openviking-api.lab. Going
      ### through HAProxy would leave this node, terminate TLS at firebat and
      ### come back to radxa for every `fs/ls`; the firewall entry in
      ### services.tf admits this host to 1933 directly instead.
      ###
      ### PUBLIC_ORIGIN is what the browser sees, and the redirect URI and the
      ### Origin check are both derived from it. It has to be the HAProxy
      ### hostname even though nothing here binds it.
      ###
      ### AUTH_MODE=vault-oidc: the person signs in at Vault's own page, this
      ### trades the ID token that comes back for a Vault token on the
      ### `jwt-lab` mount, mints `identity/oidc/token/openviking` as them and
      ### revokes the login token. No password reaches this process, which is
      ### what puts the second factor at Vault rather than in a form here -- and
      ### a form here could not answer an MFA challenge.
      ###
      ### The MINTED token is the credential every later request carries, not
      ### the ID token: OpenViking pins the identity-token issuer and audience
      ### (services/openviking/ov.conf.json) and refuses a provider token. Its
      ### ov_account/ov_user claims are the identity, which is why IDENTITY_FROM,
      ### OV_ACCOUNT and every KEY_SOURCE setting are unread here and absent.
      ###
      ### VAULT_USERPASS_MOUNT is gone with the password form. The mount still
      ### carries every human login; this job no longer speaks to it.
      ###
      ### OV_TIMEOUT_MS is 60s because `search/grep` takes about twenty seconds
      ### per term against this cluster while everything else answers in under
      ### one. The SDK's timeout is milliseconds, unlike the Python SDK's
      ### seconds.
      env {
        OV_URL         = "http://${openviking_host}:1933"
        OV_TIMEOUT_MS  = "60000"
        OV_ROOT        = "viking://user/{user}"
        OV_SHARED_ROOT = "viking://resources"

        AUTH_MODE       = "vault-oidc"
        OIDC_ISSUER     = "${vault_oidc_issuer}"
        VAULT_ADDR      = "${vault_addr}"
        VAULT_JWT_MOUNT = "${vault_jwt_mount}"
        VAULT_JWT_ROLE  = "${vault_jwt_role}"
        VAULT_OIDC_ROLE = "${vault_oidc_role}"

        HOST          = "0.0.0.0"
        PORT          = "4182"
        PUBLIC_ORIGIN = "${ov_dash_public_origin}"

        SESSION_TTL_SECONDS   = "28800"
        SESSION_COOKIE_SECURE = "true"
      }

      ### SESSION_SECRET alone, as an env file rather than an env block: it is
      ### a credential and belongs in the per-alloc secrets/ tmpfs, not in the
      ### jobspec Nomad stores and `nomad job inspect` prints.
      ###
      ### The path is under this job's own prefix, which is all the
      ### nomad-workloads role grants a read on -- any other job's path renders
      ### 403 and the task never starts. So no dedicated Vault role is needed
      ### here, and none is needed for the sign-in either: the identity token
      ### is minted with the PERSON's Vault token, not this workload's.
      template {
        data        = <<-EOF
        {{- with secret "${ov_dash_session_secret}" }}
        SESSION_SECRET={{ .Data.data.session_secret }}
        {{- end }}
        EOF
        destination = "secrets/ov-dash.env"
        env         = true
        change_mode = "restart"
      }

      ### The OIDC client's id and secret, written by the INFRASTRUCTURE root
      ### when Vault mints the client (infrastructure/secrets.tf). Both come
      ### from KV rather than the env block above, because the secret would
      ### otherwise sit in the jobspec Nomad stores and `nomad job inspect`
      ### prints. The id is not a secret and rides along to keep one source for
      ### the pair.
      ###
      ### Its own destination, NOT secrets/ov-dash.env above. Two templates
      ### writing one file leaves the last to win and drops the other's
      ### variable with nothing logged.
      template {
        data        = <<-EOF
        {{- with secret "${ov_dash_oidc_client}" }}
        OIDC_CLIENT_ID={{ .Data.data.client_id }}
        OIDC_CLIENT_SECRET={{ .Data.data.client_secret }}
        {{- end }}
        EOF
        destination = "secrets/ov-dash-oidc.env"
        env         = true
        change_mode = "restart"
      }

      ### No `memory_max`. Oversubscription is off at the server, so the
      ### scheduler zeroes it and the client sets the cgroup from `memory`
      ### alone -- it would read as headroom that does not exist. Measured on
      ### this cluster; see the long note in services/embark.hcl.
      ###
      ### So `memory` is the enforced cap, and 512 rather than an idle Node
      ### server's ~100 MB because a folder download is zipped in this process
      ### with fflate. That is the one operation that can spike, and an
      ### OOM-killed alloc signs every session out. orangepi4a has the room
      ### now that phoenix is gone.
      resources {
        cpu    = 200
        memory = 512
      }
    }
  }
}
