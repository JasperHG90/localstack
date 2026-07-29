eval: B1-bifrost-native-auth-and-virtual-keys

Definition of Done: Bifrost authenticates with its own
`governance.auth_config` (admin creds from Vault
`default/bifrost/credentials`), inference is gated by
`enforce_auth_on_inference` + a Terraform-issued Hermes virtual key
stored at `default/hermes/bifrost`, HAProxy no longer gates the bifrost
backend, and Prometheus scrapes `/metrics` via a dedicated `basic_auth`
job using a synced copy of the admin creds — with no bootstrap Vault
policy change. All assertions are static (against the rendered HCL/TF in
`deployments/`); the plan says do NOT `terraform apply` unless the
operator asks.

Scorer: one deterministic script (`grep`/parse over the cited files)
counts each row pass/fail. A row passes only when its Expected structural
requirement is present. Overall threshold: 9/9 rows pass.

| Behavior | Input | Expected | Scorer | Threshold |
|---|---|---|---|---|
| Bifrost enables its own native auth and gates inference | `deployments/applications/services/bifrost.hcl` config.json template | Contains `governance.auth_config` with `is_enabled` true, `admin_username` referencing `env.BIFROST_ADMIN_USERNAME`, `admin_password` referencing `env.BIFROST_ADMIN_PASSWORD`, and `client.enforce_auth_on_inference` true | deterministic: grep the bifrost.hcl config.json template for the four fields/values | 100% |
| Bifrost admin creds come from Vault, not inlined | `bifrost.hcl` env template + `deployments/applications/services.tf` `nomad_job.bifrost` | A Nomad env template renders `BIFROST_ADMIN_USERNAME`/`BIFROST_ADMIN_PASSWORD` from `${bifrost_credentials_secret}`, and the job passes `bifrost_credentials_secret = "${var.secret_mount}/data/default/bifrost/credentials"` | deterministic: grep for the env template vars and the `default/bifrost/credentials` path in services.tf | 100% |
| Hermes uses the Terraform-issued key, not the hardcoded value | `deployments/applications/services/hermes.hcl` + `services.tf` `nomad_job.hermes` | The literal `BIFROST_API_KEY=hermes-local` is absent from hermes.hcl; `BIFROST_API_KEY` is read from a Vault secret; `nomad_job.hermes` has `depends_on = [vault_kv_secret_v2.bifrost_hermes_key]` | deterministic: grep hermes.hcl for no `hermes-local`, a `{{ with secret }}` for the key, and the depends_on in services.tf | 100% |
| Hermes virtual key is allow-all (no deny-all footgun) | `services.tf` (or `secrets.tf`) `bifrost_virtual_key "hermes"` | `provider_configs` covers both `ollama` and `gemini`, each with `key_ids = ["*"]` and `allowed_models = ["*"]` | deterministic: grep the resource for both providers and the two allow-all lists | 100% |
| Virtual key stored under Hermes's own Vault prefix | `deployments/applications/secrets.tf` `vault_kv_secret_v2 "bifrost_hermes_key"` | Secret name is `default/hermes/bifrost` with field `API_KEY` sourced from `bifrost_virtual_key.hermes.value` | deterministic: grep for `default/hermes/bifrost`, `API_KEY`, and the value reference | 100% |
| HAProxy no longer gates Bifrost (but still gates phoenix/mlflow) | `deployments/infrastructure/services/haproxy.hcl` `backend bifrost` | The bifrost backend has no `http-request auth` line; the `openfang_users` userlist and the phoenix + mlflow `http-request auth` lines remain | deterministic: grep for absence of auth in `backend bifrost`, presence of userlist + 2 other auth lines | 100% |
| Prometheus scrapes /metrics with basic_auth via a dedicated job | `deployments/infrastructure/services/prometheus.hcl` + `bifrost.hcl` | A `- job_name: bifrost` scrape job with a `basic_auth:` block whose username/password come from a Vault template reading `default/prometheus/bifrost-admin`; the bifrost service tags no longer include `prometheus`; the prometheus task has a `vault {}` block | deterministic: grep prometheus.hcl for the bifrost job + basic_auth + vault block; grep bifrost.hcl tags for no `prometheus` | 100% |
| Synced admin-creds copy exists in the infra layer | `deployments/infrastructure/secrets.tf` + `services.tf` `nomad_job.prometheus` | An ephemeral read of `default/bifrost/credentials` and a `vault_kv_secret_v2` writing `default/prometheus/bifrost-admin` with `username`/`password`; `nomad_job.prometheus` passes a `bifrost_admin_secret` var | deterministic: grep secrets.tf for the ephemeral read + the write path/fields; grep services.tf prometheus job for the var | 100% |
| Bootstrap Vault policy untouched (no cross-prefix grant) | `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` | The file is unchanged from main: only the per-job `secret/data/<ns>/<job_id>/*` grant, no new `default/bifrost/credentials` grant | deterministic: `git diff main -- <file>` is empty (or grep shows no `default/bifrost/credentials` grant) | 100% |

signed-off-by: JasperHG90 2026-07-29