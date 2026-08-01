---
verdict: pass
plan: c37d3b79ec647e756554d458efd19ddeb205ad0763c52b128a60c71a93680a63
---

# Premise verdict: SOUND

Every repo-verifiable load-bearing assumption (P1-P8) HOLDS against the
actual code at the cited anchors. The external-software premises
(Bifrost `governance.auth_config` field names, `enforce_auth_on_inference`,
`bifrost_virtual_key` schema) are UNCERTAIN because I cannot reach the
live schema or the AirHelp-OSP/bifrost provider docs from here, but the
repo itself corroborates the two highest-blast-radius external claims
(`auth_config.is_enabled` exists; enabling it forces `basic_auth` on
`/metrics`), and the plan cites its external sources explicitly. The
plan is transparent about the unverified bits and its approach is
defensive (setting `key_ids=["*"]` is safe whether or not the
deny-all-on-omission behavior holds).

## Per-assumption findings

### P1 HAProxy bifrost auth + shared openfang_users userlist — HOLDS

- `deployments/infrastructure/services/haproxy.hcl:157` has
  `http-request auth unless { http_auth(openfang_users) }` inside
  `backend bifrost`.
- `haproxy.hcl:88-89` defines `userlist openfang_users` with
  `user admin insecure-password ${openfang_password}`.
- `haproxy.hcl:143` (phoenix) and `haproxy.hcl:153` (mlflow) reuse the
  same userlist. The userlist must stay; the plan correctly removes only
  the bifrost backend line.

### P2 Bifrost config.json is a Nomad template; bare vault {} grants
default/bifrost/* read; no policy change — HOLDS

- `deployments/applications/services/bifrost.hcl:81-122` is the
  config.json `template` block (declarative source of truth).
- `bifrost.hcl:56` is a bare `vault {}`.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-7`
  grants `read` on `secret/data/<namespace>/<job_id>/*`. With
  `secret_mount = "secret"` (confirmed in
  `deployments/applications/vars/prod.tfvars:1` and
  `deployments/infrastructure/vars/prod.tfvars:1`), the bifrost job gets
  `secret/data/default/bifrost/*`. Reading
  `default/bifrost/credentials` needs no policy change. Confirmed.

### P3 Bifrost tagged "prometheus"; scraped by shared consul_services
job that cannot carry per-target basic_auth — HOLDS

- `bifrost.hcl:29` tags include `"prometheus"`.
- `bifrost.hcl:26-29` comment explicitly warns that enabling
  `auth_config.is_enabled` requires `basic_auth` on the `/metrics`
  scrape.
- `deployments/infrastructure/services/prometheus.hcl:125-139` is the
  `consul_services` job using `consul_sd_configs` + relabeling; it has
  no per-target `basic_auth` hook. Dropping the tag and adding a
  dedicated static job is the right shape.

### P4 Hermes reaches Bifrost over loopback, hardcoded
BIFROST_API_KEY=hermes-local — HOLDS

- `deployments/applications/services/hermes.hcl:158` sets
  `base_url="http://127.0.0.1:8080/v1"` (loopback, not HAProxy).
- `hermes.hcl:209` has `BIFROST_API_KEY=hermes-local` in the `.env`
  template.
- `hermes.hcl:454` has `BIFROST_API_KEY = "hermes-local"` in the hermes
  task `env {}` block. Both cited anchors exact.

### P5 Hermes bare vault {} grants default/hermes/* only — HOLDS

- `hermes.hcl:40` (config prestart task) and `hermes.hcl:385` (hermes
  task) are bare `vault {}` blocks.
- Per the nomad-workloads policy template (P2), Hermes gets
  `secret/data/default/hermes/*`. Storing the issued key at
  `default/hermes/bifrost` is the correct prefix; no policy change.
  Confirmed.

### P6 Prometheus has no vault {}; role grants default/prometheus/* only;
synced-copy avoids bootstrap change; infra terraform has KV2 access —
HOLDS (minor uncertainty noted by the plan)

- `prometheus.hcl` has no `vault {}` block anywhere (read in full,
  lines 1-153).
- The nomad-workloads role grants `secret/data/default/prometheus/*`,
  so a synced copy at `default/prometheus/bifrost-admin` is readable by
  the prometheus job with no policy change.
- `deployments/infrastructure/secrets.tf:15-66` writes
  `vault_kv_secret_v2` resources across `default/minio`,
  `default/openfang`, `default/grafana`, `default/postgres`, and
  `deployments/infrastructure/acme.tf` writes `default/haproxy/tls`. The
  infra vault provider (`deployments/infrastructure/providers.tf:28`,
  bare `provider "vault" {}`) also creates `vault_mount.kvv2`
  (`secrets.tf:2-7`), which implies mount-level administrative
  privileges. Reading `default/bifrost/credentials` is very likely in
  scope. The plan itself flags this as a thing to confirm
  (`secrets.tf` code surface: "Confirm the infra vault provider token
  can read `default/bifrost/credentials`"). UNCERTAIN on the exact
  token scopes but low risk given the token manages the mount.

### P7 Credentials-secret field convention is username/password — HOLDS

- `deployments/infrastructure/secrets.tf:37-44` (openfang_basic_auth:
  `username`/`password`), `:52-58` (grafana_admin), `:74-80`
  (postgres_root).
- `deployments/applications/secrets.tf:1-9` (postgres_credentials),
  `:11-18` (phoenix_db), `:22-29` (memex_db), `:53-60` (mlflow_db) all
  use `username`/`password`. Convention confirmed. The new
  `default/prometheus/bifrost-admin` and the read of
  `default/bifrost/credentials` using `username`/`password` matches.

### P8 nomad_job.prometheus location; var.secret_mount in both layers;
applications/providers.tf ephemeral pattern — HOLDS

- `deployments/infrastructure/services.tf:334-339` is
  `nomad_job.prometheus`.
- `deployments/infrastructure/variables.tf:1` and
  `deployments/applications/variables.tf:1` both declare
  `variable "secret_mount"`.
- `deployments/applications/providers.tf:40-53` shows the
  `ephemeral.vault_kv_secret_v2` pattern for minio and postgres
  providers. The bifrost provider mirroring it is consistent.
- `deployments/applications/services.tf:174-192` is `nomad_job.bifrost`
  with `bifrost_version = "1.6.2"` at `:180` (corroborates the
  v1.5.0+ transport compatibility claim). `:118-144` is
  `nomad_job.hermes`. `:182-189` are the externally-seeded
  ollama/gemini secret comments.

## External-software premises (cannot verify from the repo)

- `governance.auth_config` with `is_enabled`/`admin_username`/
  `admin_password`, `env.` prefix, top-level `auth_config` deprecated:
  UNCERTAIN. The repo corroborates `auth_config.is_enabled` exists
  (`bifrost.hcl:26-29` comment) and the config.json `$schema` is
  `https://www.getbifrost.ai/schema` (`bifrost.hcl:84`), but the
  specific field names and the env.-prefix convention are not
  verifiable from the repo. I cannot reach the live schema URL from
  here.
- `client.enforce_auth_on_inference: true` gates `/v1/*`: UNCERTAIN,
  not verifiable from the repo.
- `/metrics` requires `basic_auth` when auth enabled; whitelisting
  `/metrics` NOT supported: HOLDS. Corroborated by the repo's own
  comment at `bifrost.hcl:26-29`.
- `bifrost_virtual_key` schema: `key_ids` omitted/`[]` = deny all on
  v1.5.0+; `value` set only on create; required `name`; nested
  `provider_configs` with `provider` (req), `allowed_models`/`key_ids`/
  `weight` (opt): UNCERTAIN. The AirHelp-OSP/bifrost provider is not
  present in `.terraform.lock.hcl` (it is a new addition) and I cannot
  reach the registry docs. The plan's defensive choice
  (`allowed_models=["*"]`, `key_ids=["*"]`) is safe under either
  interpretation of the omit behavior, so uncertainty here is low
  risk.

## Most dangerous assumption

The `governance.auth_config` field-name/shape premise (the
UNCERTAIN external claim). If the live schema does not accept
`is_enabled`/`admin_username`/`admin_password` under
`governance.auth_config` (or rejects the `env.` prefix), Bifrost fails
to start with an invalid config, which simultaneously locks the
dashboard AND breaks Hermes inference (highest blast radius, per the
plan's own risk note). Mitigation: the implementer must re-confirm
against `https://www.getbifrost.ai/schema` and the governance docs
before apply; `terraform validate` will not catch a wrong JSON value
shape (it is a stringified heredoc), so the first signal would be at
Bifrost alloc start. The plan already cites the schema URL; the
implementer should open it.

## Contract hygiene

- Real code surface with resolved anchors: every cited `path:line` in
  §4 and §7 resolves to the thing the plan claims (verified
  haproxy.hcl:88-89,143,153,157; bifrost.hcl:26-29,29,31-36,56,59-76,
  81-122,84; prometheus.hcl:125-139,90-101; hermes.hcl:158,209,387-412,
  454; services.tf:118-144,174-192,180,182-189,334-339;
  providers.tf:40-53; secrets.tf:15; variables.tf:1; the nomad-workloads
  policy template).
- Discovered gates: `.loop/config.json` `gates` is `just pre_commit`;
  the plan §8 cites exactly that. The plan correctly notes neither
  applications nor infrastructure justfile has a `validate` recipe
  (confirmed: only init/apply/destroy) and prescribes `terraform
  -chdir=... validate` after `just init`. Accurate.
- Explicit non-goals: §5 lists them (no provider-key migration, no
  budgets/rate_limits, no non-Hermes virtual keys, no bootstrap policy
  change, no phoenix/mlflow userlist migration).
- Tests homed in the code surface: no python test suite applies
  (HCL+TF only); the plan states this and lists manual verification
  instead. Consistent with the repo (no test directory for these
  layers).
- Forks surfaced: §11 Open Questions lists placement of
  `bifrost_virtual_key.hermes`, Prometheus `basic_auth` rendering, and
  apply orchestration, each with a recommendation.
- Required-fixes from the UNCERTAIN external premises: none that block
  readiness. The plan already cites its external sources and flags the
  deploy-ordering hazard. Recommend the implementer re-confirm the
  `governance.auth_config` field shape against the live schema before
  apply (the most dangerous assumption above).