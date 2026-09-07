data "consul_service" "minio" {
  name       = "minio"
  datacenter = "localstack"
}

data "consul_service" "postgres" {
  name       = "postgres-db"
  datacenter = "localstack"
}

ephemeral "vault_kv_secret_v2" "minio_admin" {
  mount = var.secret_mount
  name  = "default/minio/localstack"
}

ephemeral "vault_kv_secret_v2" "postgres_admin" {
  mount = var.secret_mount
  name  = "default/postgres/localstack"
}

### Nomad's OIDC issuer (F10). The memex server trusts it, and it must be
### byte-identical to what Nomad advertises or provider selection fails.
### Hermes was the second consumer until it moved to openviking, which
### authenticates with an API key instead of a workload-identity JWT.
locals {
  nomad_oidc_issuer = "https://nomad.lab.orangecluster.nl"

  ### Vault's `lab` OIDC provider, for HUMAN logins. Byte-identical to what
  ### Vault advertises and to the issuer in the human's client config, or
  ### provider selection by `iss` fails.
  vault_oidc_issuer = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
}

### The cross-root channel. The memex OIDC client is created in the
### infrastructure root; this reads its client_id back by static name, with no
### remote-state link. A public client returns an empty client_secret rather
### than erroring.
data "vault_identity_oidc_client_creds" "memex" {
  name = "memex"
}

### Firewall rules for application services
locals {
  firewall_rules = {
    # Phoenix on orange_pi_4a
    phoenix = {
      host     = "192.168.2.29"
      ssh_user = "orangepi"
      rules = [
        "allow from 192.168.0.0/16 to any port 6006 proto tcp",
        "allow from 192.168.0.0/16 to any port 4317 proto tcp",
      ]
    }
    # Hermes on radxa. The .46 rule was memex reaching the gateway; hermes now
    # uses openviking instead, so nothing dials 8642 from that host any more.
    # Left in place because these rules are one-way -- deleting the line here
    # removes no rule from the node.
    hermes = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.2.30 to any port 8642 proto tcp",
        "allow from 192.168.2.46 to any port 8642 proto tcp",
      ]
    }
    # Loki on ubuntu (rpi4b) — cluster nodes only. Alloy is a system job, so
    # it ships from every node and each node address must stay on this list;
    # dropping one stops that node's logs silently. 192.168.2.30 doubles as the
    # HAProxy edge, which is how browsers reach Loki. The push and query APIs
    # have no authentication, so the LAN-wide rule is gone.
    loki = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.2.30 to any port 3100 proto tcp",
        "allow from 192.168.2.29 to any port 3100 proto tcp",
        "allow from 192.168.2.46 to any port 3100 proto tcp",
        "allow from 192.168.2.47 to any port 3100 proto tcp",
        "allow from 192.168.2.50 to any port 3100 proto tcp",
      ]
    }
    # Tempo on ubuntu (rpi4b), colocated with the rest of the observability
    # stack. Same shape as the loki rule above and for the same reason: any
    # workload on any node may export traces, so every node address has to
    # stay on the OTLP list. 3200 is the query API, which only Grafana (same
    # host) and the HAProxy edge dial. Like Loki, none of these APIs
    # authenticate, so nothing here is LAN-wide.
    tempo = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules = [
        "allow from 192.168.2.47 to any port 3200 proto tcp",
        "allow from 192.168.2.30 to any port 3200 proto tcp",
        "allow from 192.168.2.30 to any port 4317 proto tcp",
        "allow from 192.168.2.29 to any port 4317 proto tcp",
        "allow from 192.168.2.46 to any port 4317 proto tcp",
        "allow from 192.168.2.47 to any port 4317 proto tcp",
        "allow from 192.168.2.50 to any port 4317 proto tcp",
        "allow from 192.168.2.30 to any port 4318 proto tcp",
        "allow from 192.168.2.29 to any port 4318 proto tcp",
        "allow from 192.168.2.46 to any port 4318 proto tcp",
        "allow from 192.168.2.47 to any port 4318 proto tcp",
        "allow from 192.168.2.50 to any port 4318 proto tcp",
      ]
    }
    # embark on jetson-orin-nano. Three named callers, not the cluster: embark
    # is reached through Bifrost (`embark/embedding`), so radxa is the only
    # node that dials the model routes and a direct consumer would have to be
    # added here on purpose. jetson-orin-nano admits itself because its own
    # Consul agent runs the health check against this address. .47 is
    # Prometheus scraping /metrics, which serves without a credential
    # (EMBARK_AUTH__GUARD_METRICS in services/embark.hcl), so this list is
    # what stands in front of it -- but these rules only ADD, and a wider rule
    # for port 8000 would outrank every one of them. memex left such a rule on
    # this host and port once (see the comment above null_resource.firewall).
    # Confirm none survives before trusting this list:
    #   ssh localstack@192.168.2.46 sudo ufw status numbered
    embark = {
      host     = "192.168.2.46"
      ssh_user = "localstack"
      rules = [
        "allow from 192.168.2.50 to any port 8000 proto tcp",
        "allow from 192.168.2.46 to any port 8000 proto tcp",
        "allow from 192.168.2.47 to any port 8000 proto tcp",
      ]
    }
    # OCI registry on ubuntu (rpi4b). Single-caller shape: only HAProxy on
    # firebat dials it, because podman and docker refuse a plain-HTTP
    # registry and no node manages registries.conf, so the edge is the only
    # way in. Port 5001 is the unauthenticated debug/health listener and is
    # deliberately absent: ubuntu's own Consul agent checks it over
    # loopback, so nothing off-node should reach it.
    registry = {
      host     = "192.168.2.47"
      ssh_user = "raspberry"
      rules    = ["allow from 192.168.2.30 to any port 5000 proto tcp"]
    }
    # Bifrost LLM gateway on radxa-dragon-q6a — single OpenAI-compatible endpoint for all agent consumers (ADR-001)
    bifrost = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.0.0/16 to any port 8080 proto tcp",
      ]
    }
    # Dash (landing page) on radxa-dragon-q6a (L3), colocated with
    # oauth2-proxy. oauth2-proxy reaches it over loopback
    # (127.0.0.1:8000), which never crosses this firewall; this rule is
    # the single-caller shape from infrastructure/services.tf's
    # oauth2_proxy rule, admitting only this same host in case that
    # ever changes.
    dash = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules    = ["allow from 192.168.2.50 to any port 8000 proto tcp"]
    }
    # OpenViking on radxa-dragon-q6a. Three named callers, not the LAN: this
    # was briefly `192.168.0.0/16` because headless clients had no route in at
    # all, and HAProxy fronting 1933 as openviking-api.lab.orangecluster.nl is
    # what made that unnecessary. 192.168.2.50 is the colocated oauth2-proxy,
    # .30 is HAProxy, .47 is Prometheus scraping /metrics.
    #
    # This port is NOT unauthenticated. Under auth_mode api_key every call
    # needs a user key -- /api/v1/fs/ls without one is a 401 -- so the proxy is
    # not the only thing standing here. It was under auth_mode oidc, which is
    # when this rule was written node-only.
    #
    # What IS open without a key, measured against the live service rather than
    # assumed: /ready, /health, /bot/v1/health, /docs, /openapi.json (the full
    # 113-path schema), the Studio bundle, and /metrics, which has no auth
    # dependency and is now enabled. That is why .47 is on this list and why
    # narrowing it mattered: those three callers can read the metrics, the LAN
    # cannot.
    #
    # These rules are ONE-WAY. An apply ADDS them and removes nothing, so the
    # earlier 192.168.0.0/16 rule outlives this edit and has to be deleted on
    # the node:
    #   ssh radxa@192.168.2.50 \
    #     'sudo ufw delete allow from 192.168.0.0/16 to any port 1933 proto tcp'
    # Until that runs, the host is still open LAN-wide whatever this says.
    openviking = {
      host     = "192.168.2.50"
      ssh_user = "radxa"
      rules = [
        "allow from 192.168.2.50 to any port 1933 proto tcp",
        "allow from 192.168.2.30 to any port 1933 proto tcp",
        "allow from 192.168.2.47 to any port 1933 proto tcp",
      ]
    }
  }
}

# ONE-WAY. Each rule is `ufw allow`, run once on create, and there is no
# destroy provisioner: deleting an entry above destroys the Terraform resource
# and leaves the rule live on the host. Narrowing a rule set is therefore two
# steps, and `terraform apply` is only the first -- finish it by hand:
#
#   ssh <ssh_user>@<host> sudo ufw status numbered
#   ssh <ssh_user>@<host> sudo ufw delete <n>     # highest number first
#
# The memex entry that used to sit above opened port 8000 LAN-wide on
# jetson-orin-nano. It outlived the job by a fortnight and silently subsumed
# every narrower rule embark added to the same port.
resource "null_resource" "firewall" {
  for_each = local.firewall_rules

  triggers = {
    rules = jsonencode(each.value.rules)
    host  = each.value.host
  }

  provisioner "remote-exec" {
    connection {
      host        = each.value.host
      user        = each.value.ssh_user
      private_key = file("${path.root}/../../.ssh/id_rsa")
    }

    inline = [for rule in each.value.rules : "sudo ufw ${rule}"]
  }
}

### Arize Phoenix
resource "nomad_job" "phoenix" {
  jobspec = templatefile(
    "${path.module}/services/phoenix.hcl",
    {
      phoenix_secret = vault_kv_secret_v2.phoenix_db_credentials.path
      postgres_host  = data.consul_service.postgres.service[0].node_address
      phoenix_host   = "192.168.2.29"
    }
  )
  depends_on = [postgresql_database.database]
}

### Hermes
resource "nomad_job" "hermes" {
  jobspec = templatefile(
    "${path.module}/services/hermes.hcl",
    {
      hermes_hostname = "radxa-dragon-q6a"
      hermes_host     = "192.168.2.50"
      hermes_version  = "0.21.0-1"
      # Branch, tag, or full commit SHA — pin to a SHA for reproducibility.
      external_skills_jasperhg90_ref = "main"
      openviking_host                = "192.168.2.50"
      # Must equal the ov_account this job's identity-token role emits, set in
      # the INFRASTRUCTURE root (var.vault_openviking_workloads). Two roots,
      # two states, so nothing links them but this comment: change one and the
      # job authenticates as one account while telling itself it is another.
      openviking_account = "lab"
      openviking_user    = "jasper"

      # Hermes talks to a loopback sidecar, not to OpenViking. Its endpoint has
      # to be constant for the life of the process (a running process cannot
      # have its environment changed) while the token behind it rotates every
      # few minutes, which is exactly what the sidecar exists to reconcile.
      openviking_proxy_port = 1934
      # Hermes requires the key to be set; the sidecar strips whatever arrives
      # and substitutes the real token, so this value never reaches OpenViking.
      openviking_proxy_placeholder = "unused-the-sidecar-supplies-the-token"
      ov_auth_proxy_script         = file("${path.module}/services/hermes/ov_auth_proxy.py")
      github_secret                = "${var.secret_mount}/data/default/hermes/github"
      telegram_secret              = "${var.secret_mount}/data/default/hermes/telegram"
      email_secret                 = "${var.secret_mount}/data/default/hermes/email"
      nomad_secret                 = "${var.secret_mount}/data/default/hermes/nomad"
      api_server_secret            = vault_kv_secret_v2.hermes_api_server.path
      bifrost_key_secret           = vault_kv_secret_v2.bifrost_hermes_key.path
      telegram_allowed_users       = var.telegram_allowed_users
      hermes_email_address         = var.hermes_email_address
      hermes_digest_email          = var.hermes_digest_email
      soul_md                      = file("${path.module}/services/hermes/SOUL.md")
      skills = {
        for f in fileset("${path.module}/services/hermes/skills", "**/SKILL.md") :
        trimsuffix(f, "/SKILL.md") => file("${path.module}/services/hermes/skills/${f}")
      }
    }
  )
  # Explicit dependency on the issued-key secret so terraform only deploys
  # Hermes after the Bifrost virtual key exists in Vault (operator-required).
  depends_on = [vault_kv_secret_v2.bifrost_hermes_key]
}

### Loki — central log aggregator on ubuntu (rpi4b), MinIO-backed
### Takes no secret path: loki exchanges its Workload Identity JWT through
### the credential_process helper instead of being handed a key. The Vault
### entry (vault_kv_secret_v2.loki_minio_credentials) and the static key
### behind it stay provisioned as the rollback path, and are simply not
### rendered into the job. Restoring loki to its key means restoring the
### template, the two YAML keys AND the `vault {}` block this removed.
resource "nomad_job" "loki" {
  jobspec = templatefile(
    "${path.module}/services/loki.hcl",
    { minio_host = data.consul_service.minio.service[0].node_address }
  )

  # Claim mode resolves `nomad_job_id` to this policy. Without it the STS
  # exchange returns no credential and the helper exits non-zero, which the
  # SDK reports as a credential-process failure.
  depends_on = [minio_iam_policy.loki_wi]
}

### Tempo — trace store on ubuntu (rpi4b), MinIO-backed. It belongs in this
### root because minio_iam_policy.tempo_wi, in storage.tf, is provisioned
### here.
###
### Takes no secret path: tempo exchanges its Workload Identity JWT for
### MinIO credentials rather than being handed a key. The Vault entry
### (vault_kv_secret_v2.tempo_minio_credentials) and the static key behind
### it stay provisioned as the rollback path, and are simply not rendered
### into the job.
resource "nomad_job" "tempo" {
  jobspec = templatefile(
    "${path.module}/services/tempo.hcl",
    {}
  )

  # Claim mode resolves `nomad_job_id` to this policy. Without it the STS
  # exchange fails and tempo falls back to anonymous, which surfaces as an
  # ordinary permission error rather than as a missing policy.
  depends_on = [minio_iam_policy.tempo_wi]
}

### OCI registry — container images and, via KitOps ModelKits, model
### weights. Blobs live in the `registry` MinIO bucket, so this belongs in
### this root alongside Loki and Tempo.
###
### Runs on ubuntu. It holds no local state, so placement is a capacity
### question, and firebat -- HAProxy's own node, which would have made the
### proxy hop loopback -- had no CPU headroom left behind Postgres.
###
### Every client reaches it through registry.lab.orangecluster.nl. The edge
### is required rather than optional: podman and docker refuse a plain-HTTP
### registry, and no node manages registries.conf, so TLS termination at
### HAProxy is what makes clients trust it at all. The stale LAN-wide rule
### for 5000/5001 that predated this job is removed in the infrastructure
### root, replaced by the single-caller rule in local.firewall_rules above.
### Keeps registry_auth_secret but not registry_minio_secret: the htpasswd
### still comes from Vault, while MinIO credentials now come from the
### credential_process helper. The Vault entry
### (vault_kv_secret_v2.registry_minio_credentials) and the static key behind
### it stay provisioned as the rollback path.
resource "nomad_job" "registry" {
  jobspec = templatefile(
    "${path.module}/services/registry.hcl",
    {
      registry_auth_secret = vault_kv_secret_v2.registry_auth.path
      minio_host           = data.consul_service.minio.service[0].node_address
    }
  )

  # Claim mode resolves `nomad_job_id` to this policy.
  depends_on = [minio_iam_policy.registry_wi]
}

### embark — OpenAI-compatible embedding and reranker serving.
###
### Models are NOT baked into the image. Each is a KitOps ModelKit in the
### cluster registry, pulled by a prestart task into the embark_data host
### volume. services/embark/models.json is the single source of truth for
### which ones: it drives both the pull and what embark is told to serve, so
### the two cannot drift. Round-tripped through jsondecode/jsonencode so a
### syntax error fails `terraform plan` rather than reaching the job, the same
### guard memex's auth_keys.json gets.
###
### config.toml is NOT round-tripped, because Terraform has no tomldecode: a
### typo there reaches the job and fails at embark's own startup validation
### instead of at plan time. That is why [models] lives in the JSON and only
### embark's own settings live in the TOML.
locals {
  embark_registry = "registry.lab.orangecluster.nl"

  # Served name -> ModelKit reference in the registry.
  embark_models = jsondecode(file("${path.module}/services/embark/models.json"))

  # Served name -> where the prestart task unpacks it. EMBARK_MODELS merges
  # with config.toml per key rather than replacing it (embark's docs are
  # explicit that no env var can unset a key the file declares).
  embark_models_env = jsonencode({
    for name, _ in local.embark_models : name => "/var/lib/embark/artifacts/${name}"
  })

  # The work list services/embark/pull.sh reads: one record per line, served
  # name then full registry reference. Data only -- the pull logic itself is
  # that script, not a string assembled here.
  embark_models_list = join("\n", [
    for name, ref in local.embark_models : "${name} ${local.embark_registry}/${ref}"
  ])
}

### Runs on jetson-orin-nano, the node memex used to hold.
resource "nomad_job" "embark" {
  jobspec = templatefile(
    "${path.module}/services/embark.hcl",
    {
      # Target node. embark is built for the Orin Nano's GPU.
      embark_hostname = "jetson-orin-nano"
      embark_host     = "192.168.2.46"
      # NOT the image embark's release workflow publishes. That one is the
      # portable build and carries the CPU onnxruntime wheel, and config.toml
      # asks for CUDA. Built and pushed by hand; see services/embark/README.md.
      # The `-1` is a build revision on top of base v0.1.0, not an upstream
      # version: nothing publishes embark:v0.1.0-1.
      embark_image = "ghcr.io/jasperhg90/embark-jetson:v0.2.1"

      registry_host = local.embark_registry
      # embark's OWN copy of the registry credential. The nomad-workloads
      # role grants a job read only under secret/data/default/<job_id>/*,
      # so reading the registry's own path would 403.
      registry_auth_secret = vault_kv_secret_v2.embark_registry_credentials.path
      embark_auth_secret   = vault_kv_secret_v2.embark_auth.path

      embark_models = local.embark_models_env
      models_list   = local.embark_models_list
      pull_script   = file("${path.module}/services/embark/pull.sh")
      config_toml   = file("${path.module}/services/embark/config.toml")

      # Node-local Alloy, not Tempo directly: embark should not have to know
      # where the trace backend lives. 4319, not 4317: Alloy's receiver cannot
      # use the default port, because tempo and phoenix already hold it on
      # their own nodes and Alloy is a system job. See its `network` block in
      # deployments/infrastructure/services/alloy.hcl.
      otlp_endpoint = "http://127.0.0.1:4319"
      redis_host    = "192.168.2.50"
    }
  )
}

### OpenViking's config lives in services/openviking/ov.conf.json, not inline
### in the jobspec, the same shape memex's auth_keys.json and dash's tiles.json
### already use. Two guarantees come out of that: a syntax error fails
### `terraform plan` instead of reaching the service, and
### scripts/check_openviking_config.py parses real JSON rather than a heredoc.
###
### Two kinds of token, and only one is ours. `${...}` is substituted here by
### templatefile, which ERRORS on a token with no matching variable, so a typo
### cannot reach the service as a literal. `{{ ... }}` entries are opaque to
### templatefile, which reads only `${` and `%{`, and are resolved by Nomad's
### own template engine against the secret variables openviking.hcl binds.
###
### Only values Terraform discovers at plan time are substituted. Every static
### address stays in the document, where check_openviking_config.py can assert
### it; a token there would hide the setting the check exists for.
locals {
  openviking_ov_conf = jsonencode(jsondecode(templatefile(
    "${path.module}/services/openviking/ov.conf.json",
    {
      minio_endpoint = "http://${data.consul_service.minio.service[0].node_address}:9000"
      postgres_host  = data.consul_service.postgres.service[0].node_address
    }
  )))
}

### OpenViking — context store for agents, on radxa beside Bifrost.
###
### The image is DERIVED: the upstream one carries neither ov-postgres nor
### psycopg, and storage.vectordb.backend names a dotted import path that
### OpenViking resolves at startup, so against the upstream image the backend
### does not exist. Both tags are pinned HERE and read by
### services/openviking/justfile, so what is built and what is deployed cannot
### drift. `:latest` is not a pin: it and v0.4.17.1 resolve to one index digest
### today and need not tomorrow.
###
### Built and pushed by hand; see services/openviking/README.md.
resource "nomad_job" "openviking" {
  # Registration is not readiness: the default (detach = true) returns as
  # soon as Nomad accepts the job. The provisioner below polls /ready too,
  # but this stops the apply racing ahead of the deployment.
  detach = false

  jobspec = templatefile(
    "${path.module}/services/openviking.hcl",
    {
      openviking_hostname = "radxa-dragon-q6a"
      openviking_host     = "192.168.2.50"

      openviking_base_image = "ghcr.io/volcengine/openviking:v0.4.17.1"
      openviking_image      = "ghcr.io/jasperhg90/openviking:v0.4.17.1-1"

      # The config document, already parsed, substituted and re-encoded. Every
      # host and endpoint it needs is baked in above, so the jobspec takes none
      # of them separately.
      ov_conf = local.openviking_ov_conf

      openviking_db_secret      = vault_kv_secret_v2.openviking_db_credentials.path
      openviking_minio_secret   = vault_kv_secret_v2.openviking_minio_credentials.path
      openviking_bifrost_secret = vault_kv_secret_v2.bifrost_openviking_key.path

      # The root key. It authenticates ROOT for account and user management;
      # humans use their own per-user keys (secrets.tf).
      openviking_root_key_secret = vault_kv_secret_v2.openviking_root_key.path
    }
  )

  # The database must exist before the adapter creates its tables, and the
  # Bifrost key before the config template renders. No MinIO policy dependency:
  # this job authenticates with a static key (see secrets.tf).
  depends_on = [
    postgresql_database.database,
    vault_kv_secret_v2.bifrost_openviking_key,
  ]
}

### NO ACCOUNT PROVISIONER HERE, AND THAT IS NOT AN OVERSIGHT.
###
### This root used to carry a `null_resource.openviking_users` that POSTed one
### account per person to /api/v1/admin/accounts with the root key. Under
### `auth_mode: "oidc"` that call cannot authenticate at all: the OIDC plugin
### never consults `server.root_api_key`, and it resolves every caller to role
### USER, so no admin route has a reachable credential.
###
### Leaving it in place would have failed the apply rather than been inert. Its
### trigger hashed the jobspec, the jobspec carries ov.conf.json, so flipping
### the auth mode re-ran it, and its guarded curl exits 1 on anything but
### 200/201/409.
###
### What that leaves unmeasured: whether an OpenViking read or write succeeds
### for an account whose directory tree was never initialized. The OIDC plugin
### creates nothing, and account creation used to be what initialized both
### trees. jasper and veerle already have accounts from before the flip, so
### this is only a question for the next person added.
### `scripts/ov_identity_probe.py` is what answers it.

### Dash — the cluster landing page (L3), split into a frontend and a
### backend task in the same job (L4). The tile list lives in
### services/dash/tiles.json, round-tripped through jsondecode/jsonencode
### so a syntax error fails `terraform plan` rather than reaching the job,
### the same pattern memex's auth_keys.json/auth_oidc.json already use
### (see this file's `locals.memex_auth_keys` comment). Still feeds the
### backend task only -- the frontend has no separate tile-metadata source
### (L4 P15).
locals {
  dash_tiles_json = jsonencode(jsondecode(file("${path.module}/services/dash/tiles.json")))
}

resource "nomad_job" "dash" {
  jobspec = templatefile(
    "${path.module}/services/dash.hcl",
    {
      # Two images, one per task (L4's frontend/backend split) — pinned
      # independently since the two build contexts are now separate
      # directories with no shared version.
      dash_frontend_version = "0.3.0"
      dash_backend_version  = "0.3.0"
      # Direct IP, not the `dash.lab.orangecluster.nl` edge hostname: this
      # is an internal, server-side read of Nomad's/Consul's own API, the
      # same convention prometheus.hcl's `consul_address` var already uses
      # (infrastructure/services.tf's prometheus resource) rather than the
      # devcontainer-only `localstack.local` convenience hostname.
      nomad_addr  = "http://192.168.2.30:4646"
      consul_addr = "http://192.168.2.30:8500"
      tiles_json  = local.dash_tiles_json
    }
  )
}

### registry-ui — what the cluster registry holds: KitOps ModelKits with
### their own model cards, and container images. Same two-task split dash
### uses (a static frontend, a backend that does the reading), and its own
### job so neither service can take the other down.
resource "nomad_job" "registry_ui" {
  jobspec = templatefile(
    "${path.module}/services/registry-ui.hcl",
    {
      registry_ui_frontend_version = "0.1.0"
      registry_ui_backend_version  = "0.1.0"

      # The edge hostname, not the registry's own port: that port admits
      # HAProxy's node alone (local.firewall_rules above), and TLS
      # terminates at the edge.
      registry_addr        = "https://${local.embark_registry}"
      registry_auth_secret = vault_kv_secret_v2.registry_ui_credentials.path
    }
  )
}

### Memex's auth config lives in services/memex/*.json, not inline in the job
### template (mirrors the services/hermes/ subfolder pattern), so changing a
### key or a grant is a plain-JSON edit. Both locals round-trip their file
### through jsondecode/jsonencode: that catches a syntax error in the JSON at
### plan time instead of handing memex broken config, and jsonencode always
### emits compact single-line output, which the surrounding KEY='...' env
### line requires regardless of how the source file is formatted. One side
### effect: jsonencode sorts object keys, so the rendered JSON's key order
### no longer matches either source file byte-for-byte — only array order
### (grant_rules, providers) is preserved and load-bearing.
###
### auth_keys.json needs no substitution: every `{{ .Data.data.* }}` entry is
### a Nomad/Consul-template placeholder, opaque to Terraform, resolved by
### Nomad's own template engine inside memex.hcl's `with secret` scope.
###
### auth_oidc.json carries `{{...}}` placeholders for the three values only
### Terraform knows (both issuer URLs, the human client_id); `lookup(...,
### token, token)` substitutes a known placeholder and passes any other
### string through unchanged (e.g. the literal `"memex"` audience).
### Substitution only runs over `issuer` and `audience` — a `{{...}}` token
### anywhere else in the file (e.g. a grant_rule `value`) passes through
### unchanged and would reach Nomad's own `{{ }}` template engine unresolved.
###
### Within each OIDC provider's grant_rules, ORDER IS LOAD-BEARING: memex
### takes the first matching rule and stops. The Vault provider's admin
### group must stay listed before its reader group, or a dual-tier human
### silently downgrades. See docs/memex-oidc-verification.md's V5 check.
### Both `value`s there are Vault GROUP NAMES, spelled exactly as the keys in
### `local.app_user_groups` in the OTHER Terraform root
### (deployments/infrastructure/identity.tf) — Terraform cannot enforce that
### coupling across roots.
###
### hermes holds `admin`, unscoped, deliberately: the win R5 shipped was no
### long-lived secret on the host, NOT less privilege, and narrowing it to
### writer + vault_ids was left as an explicit follow-up
### (.loop/archive/R5-rollout-memex-oidc-auth/plan.md, Q3).
locals {
  memex_auth_keys = jsonencode(jsondecode(file("${path.module}/services/memex/auth_keys.json")))

  memex_auth_oidc_substitutions = {
    "{{nomad_oidc_issuer}}"    = local.nomad_oidc_issuer
    "{{vault_oidc_issuer}}"    = local.vault_oidc_issuer
    "{{memex_oidc_client_id}}" = data.vault_identity_oidc_client_creds.memex.client_id
  }

  memex_auth_oidc = jsonencode([
    for provider in jsondecode(file("${path.module}/services/memex/auth_oidc.json")) : merge(
      provider,
      {
        issuer   = lookup(local.memex_auth_oidc_substitutions, provider.issuer, provider.issuer)
        audience = [for a in provider.audience : lookup(local.memex_auth_oidc_substitutions, a, a)]
      }
    )
  ])
}

### No-op output whose only job is a plan-time guard on auth_oidc.json's
### grant_rule field names. memex's own OidcGrantRule model ignores unknown
### keys (pydantic's extra='ignore' default) rather than rejecting them, and
### a rule with no vault_ids is unrestricted — so a typo like "vault_id"
### for "vault_ids" is silently dropped server-side and silently widens that
### grant to every vault. Terraform can't see memex's schema, but it can
### refuse to plan a key name outside it.
output "memex_auth_oidc_shape_check" {
  value       = null
  description = "No-op: exists to carry the precondition below."
  precondition {
    condition = alltrue([
      for provider in jsondecode(local.memex_auth_oidc) : alltrue([
        for rule in provider.grant_rules :
        length(setsubtract(keys(rule), ["claim", "value", "policy", "vault_ids", "read_vault_ids"])) == 0
      ])
    ])
    error_message = "A grant_rule in services/memex/auth_oidc.json has a key outside memex's OidcGrantRule schema (claim, value, policy, vault_ids, read_vault_ids). memex ignores unknown keys rather than rejecting them, so this is very likely a typo that would silently change the grant's scope — fix the field name."
  }
}

### Memex
###
### Staged, not dead. Commented out to free jetson-orin-nano for embark, which
### needs the GPU there and will not fit beside memex's ~6.5 GB. Uncomment when
### memex has somewhere else to run: change `memex_host` to that node first, or
### it lands back on the Jetson and one of the two stops placing.
# resource "nomad_job" "memex" {
#   jobspec = templatefile(
#     "${path.module}/services/memex.hcl",
#     {
#       memex_postgres_secret = vault_kv_secret_v2.memex_db_credentials.path
#       memex_minio_secret    = vault_kv_secret_v2.memex_minio_credentials.path
#       memex_auth_secret     = vault_kv_secret_v2.memex_auth_keys.path
#       postgres_host         = data.consul_service.postgres.service[0].node_address
#       minio_host            = data.consul_service.minio.service[0].node_address
#       phoenix_host          = "192.168.2.29"
#       memex_host            = "192.168.2.46"
#       memex_auth_keys       = local.memex_auth_keys
#       memex_auth_oidc       = local.memex_auth_oidc
#       bifrost_host          = "192.168.2.50"
#       memex_version         = "1.2.0"
#       # Bifrost virtual key issued to Memex (default/memex/bifrost). Memex's
#       # default/extraction/reflection models all call Bifrost /v1 with this key.
#       bifrost_key_secret = vault_kv_secret_v2.bifrost_memex_key.path
#     }
#   )
#   # Deploy Memex only after its Bifrost key exists in Vault.
#   depends_on = [postgresql_database.database, vault_kv_secret_v2.bifrost_memex_key]
# }

### Bifrost — LLM gateway: load-balances two Ollama Cloud keys, falls back to Gemini (ADR-001)
resource "nomad_job" "bifrost" {
  jobspec = templatefile(
    "${path.module}/services/bifrost.hcl",
    {
      bifrost_hostname = "radxa-dragon-q6a"
      bifrost_host     = "192.168.2.50"
      bifrost_version  = "2.0.0"
      # Externally seeded in Vault (not Terraform-managed):
      #   vault kv put secret/default/bifrost/ollama-personal API_KEY=...
      #   vault kv put secret/default/bifrost/ollama-xebia    API_KEY=...
      #   vault kv put secret/default/bifrost/gemini          GOOGLE_API_KEY=...
      #   vault kv put secret/default/bifrost/credentials username=... password=...
      ollama_personal_secret     = "${var.secret_mount}/data/default/bifrost/ollama-personal"
      ollama_xebia_secret        = "${var.secret_mount}/data/default/bifrost/ollama-xebia"
      gemini_secret              = "${var.secret_mount}/data/default/bifrost/gemini"
      bifrost_credentials_secret = "${var.secret_mount}/data/default/bifrost/credentials"
      # config_store is Postgres (see bifrost.hcl); the bifrost role/DB are
      # provisioned in database.tf and the creds stored at default/bifrost/db.
      bifrost_postgres_host = data.consul_service.postgres.service[0].node_address
      bifrost_db_secret     = vault_kv_secret_v2.bifrost_db_credentials.path
      # embark as a custom OpenAI-compatible provider, reached as
      # "embark/embedding". Not user-facing: embark's firewall admits cluster
      # nodes only, so Bifrost is how anything gets embeddings.
      embark_host       = "192.168.2.46"
      embark_key_secret = vault_kv_secret_v2.bifrost_embark_key.path
    }
  )
  # Bifrost migrates its config_store schema on startup, so the DB must exist
  # first. The embark key must exist before the provider template renders.
  depends_on = [postgresql_database.database, vault_kv_secret_v2.bifrost_embark_key]
}

# Admin creds the bifrost provider authenticates with and Bifrost itself reads
# via env.BIFROST_ADMIN_USERNAME/PASSWORD. Externally seeded (see comment above).
ephemeral "vault_kv_secret_v2" "bifrost_admin" {
  mount = var.secret_mount
  name  = "default/bifrost/credentials"
}

# The bifrost terraform provider has no retry/wait, so a virtual_key create can
# 401/refuse against a not-yet-ready Bifrost. This gate polls /health (always
# whitelisted, even with auth enabled) until the gateway is up before the key
# resource runs.
resource "null_resource" "bifrost_ready" {
  depends_on = [nomad_job.bifrost]

  # Carry the endpoint and a hash of the jobspec. The jobspec hash forces this
  # gate to replace (and re-poll /health) on every Bifrost redeploy, so virtual
  # keys (which depend on this resource) are only touched after the gateway is
  # back up. Carrying the endpoint in triggers also makes the bifrost provider
  # (providers.tf) depend on this resource: the provider cannot configure until
  # Bifrost is up, instead of racing a restart against a hardcoded IP.
  triggers = {
    endpoint = "http://192.168.2.50:8080"
    jobspec  = sha1(nomad_job.bifrost.jobspec)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      for i in $(seq 1 60); do
        if curl -fsS ${self.triggers.endpoint}/health >/dev/null 2>&1; then
          echo "bifrost ready"
          exit 0
        fi
        echo "waiting for bifrost /health..."
        sleep 2
      done
      echo "bifrost did not become ready" >&2
      exit 1
    EOT
  }
}

# Hermes virtual key: allow-all on ollama + gemini + embark. allowed_models=["*"] is the
# wildcard (Bifrost IsUnrestricted); key_ids=["*"] allows all upstream keys.
# Note: the wildcard does NOT bypass Bifrost's model catalog — a requested model
# must still exist in the catalog for the provider (plugins/governance/resolver.go
# IsModelAllowedForProvider). ollama models not in the catalog 403 as
# "Model not allowed for this virtual key" regardless of this allowlist.
# NOTE: keep provider_configs in ALPHABETICAL order by `provider`. The Bifrost
# API returns this list sorted, but the Terraform provider models it as an
# ordered list, so any other order fails the post-apply consistency check with
# "produced an unexpected new value: .provider_configs[N].provider" -- the
# write lands, the plan errors. Adding "embark" after "ollama"/"gemini" is what
# first hit it.
resource "bifrost_virtual_key" "hermes" {
  name = "hermes"

  provider_configs = [
    { provider = "embark", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]

  depends_on = [null_resource.bifrost_ready]
}

# Memex virtual key: allow-all on ollama + gemini + embark. Same wildcard
# semantics as the Hermes key: allowed_models=["*"], key_ids=["*"]. See the
# Hermes comment for the model-catalog caveat.
resource "bifrost_virtual_key" "memex" {
  name = "memex"

  provider_configs = [
    { provider = "embark", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "gemini", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]

  depends_on = [null_resource.bifrost_ready]
}

# OpenViking virtual key.
# embark carries embedding and rerank; ollama carries the VLM that writes image
# summaries. Alphabetical by `provider` -- see the Hermes key's comment for why
# any other order fails the post-apply consistency check.
#
# `allowed_models = ["*"]` does NOT bypass Bifrost's model catalog. Only
# glm-5.3-flash was measured to accept an image: plain glm-5.3, glm-5.2,
# glm-5.1 and both deepseek-v4 variants are in the catalog and answer text
# while refusing image input with "this model does not support image input".
resource "bifrost_virtual_key" "openviking" {
  name = "openviking"

  provider_configs = [
    { provider = "embark", allowed_models = ["*"], key_ids = ["*"], weight = 1 },
    { provider = "ollama", allowed_models = ["*"], key_ids = ["*"], weight = 1 }
  ]

  depends_on = [null_resource.bifrost_ready]
}
