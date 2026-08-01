---
verdict: pass
tree: aebdbe00f6445156d3fb8422e308d5b6499d1b57
---

# Adversarial review: B1-bifrost-native-auth-and-virtual-keys

## Gates re-run independently

- `python3 .loop/evals/B1-bifrost-native-auth-and-virtual-keys.scorer.py` ->
  9/9 scenarios passed.
- `just pre_commit` -> all hooks green (check json, check yaml, detect
  private key, fix end of files, Nomad Format, Terraform Format
  -check -recursive, Terraform Validate per root).
- `git diff main -- bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  -> empty (bootstrap policy untouched, confirmed by scorer scenario 9).

## Load-bearing claims verified

1. **governance.auth_config enables native auth and gates inference.**
   `deployments/applications/services/bifrost.hcl:94-100` declares
   `governance.auth_config` with `is_enabled: true`,
   `admin_username: "env.BIFROST_ADMIN_USERNAME"`,
   `admin_password: "env.BIFROST_ADMIN_PASSWORD"`. `client.enforce_auth_on_inference: true`
   is set at `bifrost.hcl:92`. Both reference env vars, not inlined secrets.

2. **Admin creds rendered from Vault, not inlined.** `bifrost.hcl:61-64`
   renders `BIFROST_ADMIN_USERNAME`/`BIFROST_ADMIN_PASSWORD` from
   `${bifrost_credentials_secret}` via a Nomad `{{ with secret }}` template.
   `deployments/applications/services.tf:196` passes
   `bifrost_credentials_secret = "${var.secret_mount}/data/default/bifrost/credentials"`.
   The `vault {}` block at `bifrost.hcl:56` already grants the task read on
   `default/bifrost/*` via the existing nomad-workloads role, so no policy
   change is needed (and none was made).

3. **Virtual key is allow-all on both providers (no deny-all footgun).**
   `deployments/applications/services.tf:233-242` defines
   `bifrost_virtual_key "hermes"` with `provider_configs` covering both
   `"ollama"` and `"gemini"`, each with `key_ids = ["*"]` and
   `allowed_models = ["*"]`. A deny-all here would 403 Hermes inference;
   both are correctly allow-all.

4. **Key stored under Hermes's own Vault prefix; explicit depends_on.**
   `deployments/applications/secrets.tf:104-113` writes
   `vault_kv_secret_v2 "bifrost_hermes_key"` to `default/hermes/bifrost`
   with field `API_KEY` sourced from `bifrost_virtual_key.hermes.value`.
   Hermes's nomad-workloads role grants read only on `default/hermes/*`,
   so this prefix is correct (not `default/bifrost/*`).
   `services.tf:147` adds `depends_on = [vault_kv_secret_v2.bifrost_hermes_key]`
   to `nomad_job.hermes` (operator-required explicit dependency).

5. **Infra synced copy uses a data source, not ephemeral.**
   `deployments/infrastructure/secrets.tf:98-100` declares
   `data "vault_kv_secret_v2" "bifrost_admin"` (read of
   `default/bifrost/credentials`). The write at `:103-115`
   (`vault_kv_secret_v2 "prometheus_bifrost_admin"`) sources
   `username`/`password` from `data.vault_kv_secret_v2.bifrost_admin.data.*`
   into `data_json`. This is correct: ephemeral values cannot flow into the
   state-persisted `data_json` attribute, so a `data` source is required.
   The applications-layer `ephemeral "vault_kv_secret_v2" "bifrost_admin"`
   at `services.tf:202-205` feeds the `provider "bifrost"` block only
   (`providers.tf:59-63`), mirroring the minio/postgres provider pattern.
   That is the allowed use of ephemeral.

6. **HAProxy still gates phoenix/mlflow, drops bifrost.**
   `deployments/infrastructure/services/haproxy.hcl:156` `backend bifrost`
   has no `http-request auth` line (removed). `:143` (phoenix) and `:153`
   (mlflow) retain `http-request auth unless { http_auth(openfang_users) }`.
   The `userlist openfang_users` at `:88` remains. Exactly 2 auth lines
   remain.

7. **Prometheus dedicated basic_auth scrape job; bifrost tag dropped.**
   `deployments/infrastructure/services/prometheus.hcl:65` adds `vault {}`
   to the prometheus task (previously none). `:113-119` adds a dedicated
   `- job_name: bifrost` with `metrics_path: /metrics`, `basic_auth`
   rendering `username`/`password` from
   `{{ with secret "${bifrost_admin_secret}" }}`. `services.tf:337` passes
   `bifrost_admin_secret = vault_kv_secret_v2.prometheus_bifrost_admin.path`.
   `bifrost.hcl:29` drops `"prometheus"` from the service tags so the shared
   `consul_services` job stops scraping it (would 401).

8. **Readiness gate polls /health before the key resource.**
   `services.tf:211-229` `null_resource "bifrost_ready"` depends_on
   `nomad_job.bifrost` and polls `http://192.168.2.50:8080/health` (60 x 2s)
   via `local-exec`. `bifrost_virtual_key.hermes` depends_on
   `null_resource.bifrost_ready` (`:241`). The chain
   bifrost -> readiness -> virtual_key -> vault_secret -> hermes is sound.
   The `/health` whitelisting assumption is load-bearing: if `/health`
   required auth, the unauthenticated `curl -fsS` would 401 and the gate
   would fail safely (apply blocks, no broken state). This matches the
   plan's documented assumption.

9. **Bootstrap policy unchanged.** `git diff main` on
   `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
   is empty. No cross-prefix grant was added.

## Scope check

Every changed line traces to the ticket:
- `AGENTS.md` -- adds Bifrost to the terraform provider list (new provider).
- `deployments/applications/providers.tf` -- bifrost provider registration
  + config (ephemeral creds, mirrors minio/postgres).
- `deployments/applications/secrets.tf` -- `bifrost_hermes_key` vault secret.
- `deployments/applications/services.tf` -- ephemeral read, readiness gate,
  virtual key, hermes `bifrost_key_secret` var + depends_on, bifrost
  `bifrost_credentials_secret` var + seeding comment.
- `deployments/applications/services/bifrost.hcl` -- auth_config,
  enforce_auth_on_inference, admin-creds env template, tag drop, comment
  update.
- `deployments/applications/services/hermes.hcl` -- Vault read for
  BIFROST_API_KEY in both env templates; hardcoded `hermes-local` removed
  from static `env {}` (grep confirms no `hermes-local` remains anywhere
  under `deployments/`).
- `deployments/infrastructure/secrets.tf` -- synced copy data source + write.
- `deployments/infrastructure/services.tf` -- prometheus
  `bifrost_admin_secret` var.
- `deployments/infrastructure/services/haproxy.hcl` -- single auth line
  removed from `backend bifrost`.
- `deployments/infrastructure/services/prometheus.hcl` -- `vault {}` block
  + dedicated bifrost scrape job with basic_auth.
- `docs/haproxy_reverse_proxy.md` + `docs/monitoring.md` -- accurate,
  surgical updates reflecting the bifrost auth move.

No out-of-scope lines. No orphaned imports/vars. Style matches existing
conventions (applications secrets use `mount = var.secret_mount` with no
custom_metadata; infra secrets use `mount = vault_mount.kvv2.path` with
`delete_all_versions = false` + `custom_metadata` -- the new resources in
each layer match their layer's convention).

## Findings

None. The implementation is correct, surgical, and consistent with existing
repo patterns. All gates pass. No deny-all footgun, no wrong Vault prefix,
no missing depends_on, no stale doc, no bootstrap-policy widening.