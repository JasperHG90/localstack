---
epic = "bifrost"
priority = 200
summary = """
Replace HAProxy basic-auth gating Bifrost with Bifrost's native
governance.auth_config, gate inference via enforce_auth_on_inference +
a Terraform-managed virtual key for Hermes, and move the Prometheus
/metrics scrape to basic_auth. Prerequisite for API keys.
"""
---

# Ticket: B1-bifrost-native-auth-and-virtual-keys

## 1. Title

Stop authenticating to Bifrost through HAProxy's `http-request auth`
(shared `openfang_users` userlist). Enable Bifrost's own
`governance.auth_config` (admin user/password from Vault
`default/bifrost/credentials`), gate inference with
`client.enforce_auth_on_inference: true`, and issue Hermes a virtual key
managed by the Terraform Bifrost provider so Hermes keeps working. This is
the prerequisite for API keys.

## 2. Size / Effort

**L.** Spans two terraform layers (applications + infrastructure) plus a
new terraform provider, a cross-layer secret sync, and a deploy-ordering
hazard (Hermes breaks between the Bifrost restart and the Hermes restart).
No bootstrap change.

## 3. Triggered by

Operator request: "we currently authenticate using user/pwd via haproxy,
but this is not correct. Bifrost has its own user/password settings. We
need that if we want to set up API keys." Docs:
https://docs.getbifrost.ai/quickstart/gateway/setting-up-auth ,
https://docs.getbifrost.ai/deployment-guides/config-json/governance .

## 4. Context

- HAProxy gates the external `bifrost.lab.orangecluster.nl` endpoint with
  `http-request auth unless { http_auth(openfang_users) }`:
  `deployments/infrastructure/services/haproxy.hcl:157`. The `openfang_users`
  userlist (`haproxy.hcl:88-89`) is also used by the phoenix (`:143`) and
  mlflow (`:153`) backends — keep it.
- Bifrost runs open (no auth). Its config.json is the declarative source of
  truth, rebuilt from a Nomad template every alloc:
  `deployments/applications/services/bifrost.hcl:81-122`. The job reads its
  provider keys from Vault with a bare `vault {}` (`bifrost.hcl:56`); the
  `nomad-workloads` role grants read on `default/bifrost/*`, so reading
  `default/bifrost/credentials` needs NO policy change.
- The bifrost service comment (`bifrost.hcl:26-29`) explicitly warns that
  enabling `auth_config` requires `basic_auth` on the `/metrics` scrape.
  Bifrost is scraped by the shared `consul_services` job because its service
  tags include `"prometheus"` (`bifrost.hcl:29`); that shared job cannot
  carry per-target basic_auth (`deployments/infrastructure/services/prometheus.hcl:125-139`).
- Hermes reaches Bifrost over loopback `http://127.0.0.1:8080/v1`
  (`deployments/applications/services/hermes.hcl:158`), NOT through HAProxy,
  and sends a hardcoded `BIFROST_API_KEY=hermes-local`
  (`hermes.hcl:209` and `hermes.hcl:454`) that Bifrost currently ignores.
  Hermes uses ollama/* and gemini/* models (`hermes.hcl:218-294`).
- Hermes's bare `vault {}` grants read on `default/hermes/*` only, so any
  secret Hermes must read has to live under `default/hermes/...`.
- Prometheus currently reads NO Vault secrets — no `vault {}` block in
  `prometheus.hcl`. Its `nomad-workloads` role grants read on
  `default/prometheus/*` only.
- Repo convention for credentials secrets: fields `username`/`password`
  (postgres, memex, phoenix, mlflow, grafana). Bifrost admin creds live at
  `default/bifrost/credentials` (externally seeded, like the ollama/gemini
  keys at `deployments/applications/services.tf:182-189`).

## 5. Non-goals / out of scope

- Migrating ollama/gemini provider keys to terraform
  `bifrost_provider_key` resources (they stay in config.json; the virtual
  key uses `key_ids=["*"]`).
- Budgets / rate_limits on the Hermes virtual key.
- Virtual keys for any consumer other than Hermes.
- Any bootstrap Vault policy change (the `nomad-workloads` policy at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` is
  untouched — the Prometheus creds reach it via a synced copy under
  `default/prometheus/*`, its own prefix).
- Migrating phoenix/mlflow off the `openfang_users` HAProxy userlist.

## 6. Requirements & restrictions

- Enable `governance.auth_config` with `is_enabled: true`,
  `admin_username: "env.BIFROST_ADMIN_USERNAME"`,
  `admin_password: "env.BIFROST_ADMIN_PASSWORD"` (top-level `auth_config`
  is deprecated — use `governance.auth_config`). Source: Bifrost governance
  docs + schema (`https://www.getbifrost.ai/schema`).
- Set `client.enforce_auth_on_inference: true` so `/v1/*` requires a
  virtual key.
- Render `BIFROST_ADMIN_USERNAME`/`BIFROST_ADMIN_PASSWORD` from Vault
  `default/bifrost/credentials` (fields `username`/`password`) via a Nomad
  env template, mirroring the existing provider-key env template at
  `bifrost.hcl:59-76`. Never inline secrets in config.json (repo rule:
  secrets in Vault KV2, `CLAUDE.md`).
- Issue Hermes a virtual key via the Terraform Bifrost provider
  (`AirHelp-OSP/bifrost` ~>0.1). The resource is `bifrost_virtual_key`:
  required `name`; `provider_configs` nested fields `provider` (req),
  `allowed_models` (opt), `key_ids` (opt — OMITTED or `[]` = deny all on
  v1.5.0+, so MUST set `["*"]`), `weight` (opt). Read-only `value`
  (sensitive, set only on create). MUST set `allowed_models=["*"]` and
  `key_ids=["*"]` for both `ollama` and `gemini` provider_configs or Hermes
  gets deny-all. Source: provider docs
  `https://registry.terraform.io/providers/AirHelp-OSP/bifrost/latest/docs/resources/virtual_key`.
- Store the virtual key `value` in Vault at `default/hermes/bifrost` as
  field `API_KEY` (under Hermes's own prefix so Hermes can read it).
- Hermes reads `BIFROST_API_KEY` from that Vault path instead of the
  hardcoded `hermes-local`.
- `nomad_job.hermes` MUST `depends_on = [vault_kv_secret_v2.bifrost_hermes_key]`
  (operator-required explicit dependency "so you know it's there").
- The Bifrost provider has NO retry/wait: add a `null_resource` readiness
  gate polling `http://192.168.2.50:8080/health` until up, depends_on
  `nomad_job.bifrost`, and `bifrost_virtual_key.hermes` depends_on it.
  `/health` is always whitelisted (system route), so the Nomad http check
  on `/health` (`bifrost.hcl:31-36`) survives auth.
- Move `/metrics` scraping to a dedicated Prometheus job with `basic_auth`
  (the admin creds). Whitelisting `/metrics` is NOT supported per
  `https://docs.getbifrost.ai/features/observability/prometheus`. Drop the
  `"prometheus"` tag from the bifrost service so the shared
  `consul_services` job stops scraping it (would 401).
- Prometheus gets the admin creds from a synced copy at
  `default/prometheus/bifrost-admin` (fields `username`/`password`),
  written by the infrastructure terraform from an ephemeral read of
  `default/bifrost/credentials`. This avoids a bootstrap policy change at
  the cost of the creds living in two paths (drift risk if rotated without
  a terraform apply — note in commit).
- Remove `http-request auth unless { http_auth(openfang_users) }` from the
  HAProxy `backend bifrost` only (`haproxy.hcl:157`).
- Provider version compatibility: Bifrost provider targets HTTP transport
  v1.5.0+; repo runs bifrost v1.6.2 (`services.tf:180`). OK.
- Every changed line traces to this ticket (loop scope rule). Match
  existing HCL/TF style; surgical changes only (`CLAUDE.md` §3).

## 7. Code surface

Applications layer:
- `deployments/applications/services/bifrost.hcl` — add `governance.auth_config`
  + `client.enforce_auth_on_inference: true` to the config.json template
  (`:81-122`); add a Vault env template rendering `BIFROST_ADMIN_USERNAME`/
  `BIFROST_ADMIN_PASSWORD` from `${bifrost_credentials_secret}` (mirror
  `:59-76`); drop `"prometheus"` from service tags (`:29`); update the
  service-tag comment (`:26-29`) to reflect that auth is now enabled and
  Prometheus scrapes via a dedicated basic_auth job.
- `deployments/applications/services/hermes.hcl` — replace hardcoded
  `BIFROST_API_KEY=hermes-local` (`:209` and `:454`) with a Vault read from
  `${bifrost_key_secret}` (add a `{{ with secret }}` block to the `.env`
  template at `:181-213`; the env-block one at `:454` is consumed by the
  hermes task which already has its own env template at `:387-412` — add
  the key there instead of the static `env {}`).
- `deployments/applications/services.tf` — `nomad_job.bifrost` (`:174-192`):
  add `bifrost_credentials_secret = "${var.secret_mount}/data/default/bifrost/credentials"`
  + a `vault kv put` seeding comment. `nomad_job.hermes` (`:118-144`): add
  `bifrost_key_secret = vault_kv_secret_v2.bifrost_hermes_key.path` to the
  templatefile vars and `depends_on = [vault_kv_secret_v2.bifrost_hermes_key]`.
  Add: `ephemeral "vault_kv_secret_v2" "bifrost_admin"` (read
  `default/bifrost/credentials`), `null_resource "bifrost_ready"` (health
  poll, depends_on `nomad_job.bifrost`), `bifrost_virtual_key "hermes"`
  (depends_on `null_resource.bifrost_ready`).
- `deployments/applications/providers.tf` — register `bifrost` in
  `required_providers` (`:2-27`) and add `provider "bifrost"` using the
  ephemeral read (mirror minio/postgres providers at `:40-53`):
  `endpoint = "http://192.168.2.50:8080"`, `username`/`password` from
  `ephemeral.vault_kv_secret_v2.bifrost_admin.data.*`.
- `deployments/applications/secrets.tf` — add
  `vault_kv_secret_v2 "bifrost_hermes_key"` writing
  `default/hermes/bifrost` with `data_json = jsonencode({ API_KEY = bifrost_virtual_key.hermes.value })`,
  `depends_on = [bifrost_virtual_key.hermes]` (matches the vault_kv_secret_v2
  pattern at `:1-110`). Place `bifrost_virtual_key` here too OR in
  services.tf next to the provider resources — pick one and be consistent.

Infrastructure layer:
- `deployments/infrastructure/services/haproxy.hcl` — delete the
  `http-request auth unless { http_auth(openfang_users) }` line in
  `backend bifrost` (`:157`). Keep the userlist and the phoenix/mlflow
  auth lines.
- `deployments/infrastructure/services/prometheus.hcl` — add `vault {}` to
  the prometheus task (currently none); add a `template` rendering the
  basic_auth creds from `${bifrost_admin_secret}` into the config (or a
  separate env file consumed by the scrape config — Prometheus
  `basic_auth` must be inline in `prometheus.yml`, so render username/
  password directly into the `basic_auth:` block of the new job); add a
  dedicated `- job_name: bifrost` scrape job (static target
  `192.168.2.50:8080`, `metrics_path: /metrics`, `basic_auth`), inserted
  near the other static jobs (`:90-101`).
- `deployments/infrastructure/services.tf` — `nomad_job.prometheus`
  (`:334-339`): add `bifrost_admin_secret = "${var.secret_mount}/data/default/prometheus/bifrost-admin"`
  to the templatefile vars.
- `deployments/infrastructure/secrets.tf` — add
  `ephemeral "vault_kv_secret_v2" "bifrost_admin"` (read
  `default/bifrost/credentials`) and
  `vault_kv_secret_v2 "prometheus_bifrost_admin"` writing
  `default/prometheus/bifrost-admin` with `username`/`password` from the
  ephemeral read, `mount = vault_mount.kvv2.path` (matches `:15`). Confirm
  the infra vault provider token can read `default/bifrost/credentials`
  (it already writes `openfang_basic_auth`/`grafana_admin_credentials`,
  so it has KV2 access on the mount).

Bootstrap layer: NONE.

## 8. Tests & validation gates

- Eval (Definition of Done, signed): `.loop/evals/B1-bifrost-native-auth-and-virtual-keys.md`
  — 9 static-config guardrail scenarios (deterministic grep scorer, 100%
  threshold). The implementer writes the scorer and runs it; all 9 must pass.
- Gate (from `.loop/config.json` `gates`): `just pre_commit`. Run `just
  format` first (nomad fmt -recursive) since `.hcl` files change.
- No python/test suite applies (HCL + TF only). Validate syntax with
  `terraform fmt -check` and `terraform validate` in both
  `deployments/applications` and `deployments/infrastructure` (run via
  `terraform -chdir=...`; neither justfile has a validate recipe —
  applications/infra justfiles only have init/apply/destroy). `terraform
  validate` requires `terraform init` first to pull the new `bifrost`
  provider; run `just init` (or `terraform init`) in applications.
- Do NOT run `terraform apply` against the lab unless the operator asks.
- Manual verification the operator can run after apply (document, don't
  execute): `curl -u admin:*** http://192.168.2.50:8080/metrics` succeeds;
  unauthenticated `/v1/chat/completions` returns 401; Hermes loopback
  inference works with the issued key; Prometheus bifrost target is UP.

## 9. Risk assessment

- **Blast radius:** Bifrost (all LLM traffic), Hermes (the agent), and
  Prometheus bifrost scrape. A wrong `auth_config` value (blank creds from
  a mis-typed Vault field) locks the dashboard AND breaks Hermes inference.
- **Deploy-order hazard:** with `enforce_auth_on_inference: true`, Hermes
  is broken from the moment Bifrost restarts until Hermes restarts with the
  real key — seconds to minutes within one `terraform apply`. The
  `depends_on` chain (bifrost → readiness gate → virtual key → vault
  secret → hermes) makes terraform do this in the right order but cannot
  eliminate the window. Flag in the commit.
- **Provider no-retry:** without the `null_resource` readiness gate, the
  `bifrost_virtual_key` create can 401/refuse on a not-yet-ready Bifrost
  and fail the whole apply partway (Bifrost auth on, Hermes not yet
  redeployed → Hermes stuck broken until a re-apply).
- **Secret sync drift:** `default/prometheus/bifrost-admin` is a copy of
  `default/bifrost/credentials`. Rotating the latter without a terraform
  apply leaves Prometheus scraping with stale creds (401). Mitigation: note
  in commit; rotation must trigger `terraform apply` on infra.
- **Virtual key value not recoverable:** `bifrost_virtual_key.value` is
  set only on create and not re-readable from the API. Terraform state
  loss → the key still works in Bifrost but terraform can't recover the
  token; `terraform import` yields `value = null` → must rotate the key
  and re-issue. Back up state.
- **Reversibility:** HAProxy auth removal and config.json changes are
  git-revertible; the virtual key persists in Bifrost's SQLite store
  (`config_store`) — `terraform destroy` removes it via the provider.
- **`additionalProperties: false` on auth_config:** only the four documented
  fields are allowed; do not add extras.

## 10. Subtickets

One iteration is feasible but sequence the work in this order:

1. Applications: bifrost.hcl auth_config + enforce_auth_on_inference +
   admin-creds env template; tag/comment update. → verify: `terraform
   validate` (applications) passes; `just format` clean.
2. Applications: providers.tf bifrost provider; secrets.tf/services.tf
   ephemeral read + readiness gate + `bifrost_virtual_key.hermes` +
   `vault_kv_secret_v2.bifrost_hermes_key`; services.tf bifrost job var +
   hermes `bifrost_key_secret` + `depends_on`. → verify: `terraform
   validate` passes.
3. Applications: hermes.hcl read `BIFROST_API_KEY` from Vault. → verify:
   `terraform validate` passes.
4. Infrastructure: secrets.tf synced copy; services.tf prometheus var;
   prometheus.hcl vault block + dedicated bifrost scrape job with
   basic_auth; haproxy.hcl remove bifrost auth line. → verify:
   `terraform validate` (infrastructure) passes; `just format` clean.
5. `just pre_commit` green.

## 11. Open questions

- **Where to place `bifrost_virtual_key.hermes`** — `secrets.tf` (with the
  vault_kv_secret_v2) or `services.tf` (with the nomad_job + provider
  resources)? Recommendation: `services.tf` next to `nomad_job.bifrost` and
  the provider resources, since it is not a Vault-secret definition; keep
  `vault_kv_secret_v2.bifrost_hermes_key` in `secrets.tf` to match the
  existing vault_kv_secret_v2 pattern there.
- **Prometheus `basic_auth` rendering** — Prometheus reads
  `basic_auth.username`/`password` inline from `prometheus.yml`, which is a
  Nomad template. Render the creds directly into the `basic_auth:` block of
  the new job (the prometheus task will need `vault {}` + the secret in the
  same template that writes `prometheus.yml`). Recommendation: extend the
  existing `prometheus.yml` template (`prometheus.hcl:63-145`) with a
  `{{ with secret "${bifrost_admin_secret}" }}` block wrapping the new
  `bifrost` job's `basic_auth`.
- **Apply orchestration** — both layers must apply; prometheus basic_auth
  should land before (or with) Bifrost auth enabling, or `/metrics` scrapes
  401 silently until prometheus redeploys. Recommendation: apply
  infrastructure (prometheus + haproxy) first, then applications
  (bifrost + hermes). The operator runs the applies; the ticket only
  prepares the code.