---
epic = "switchyard"
depends_on = []
priority = 0
summary = """
Deploy NVIDIA-NeMo/Switchyard (`switchyard-server`) as a new Nomad job that
passthrough-routes to the existing Bifrost gateway, with its own inbound
auth at the HAProxy edge. Base deployment + auth only: no Hermes/opencode
cutover, no multi-tier routing config. Both design forks (build/run
mechanism; inbound-auth mechanism) are resolved as of 2026-08-22: build
off-cluster, publish once to a new private MinIO bucket, fetch via Nomad's
`artifact` + `secret` job-spec stanzas; gate the edge with a second,
Switchyard-scoped oauth2-proxy instance mirroring L1 (now `done`). Node
placement stays a live-cluster check, not a blocking fork.
"""
tags = ["switchyard", "llm", "nomad", "haproxy", "vault", "bifrost", "minio", "prometheus", "grafana"]
---

# Ticket: SY1-switchyard-deployment — Deploy Switchyard in front of Bifrost, with its own inbound auth

## 1. Title
Stand up `switchyard-server` as a new Nomad job that passthrough-routes to
Bifrost, gated at the HAProxy edge by its own inbound-auth check. Foundation
ticket for the `switchyard` epic; Hermes/opencode cutover and multi-tier
routing are explicitly out of scope and land as follow-on tickets that
`depends_on` this one.

## 2. Size / Effort
**Large.** Two Terraform roots (`deployments/applications`,
`deployments/infrastructure`), a brand-new Nomad job with no upstream
image/binary to pull, a second Switchyard-scoped oauth2-proxy instance, a
new MinIO bucket/user/credential, and this repo's first use of two Nomad
job-spec mechanisms (`artifact`, `secret`). Every piece mirrors an existing,
proven pattern (Bifrost virtual key, per-consumer Vault KV wiring,
Prometheus tag, Grafana dashboard, L1's oauth2-proxy shape) — the size
comes from the volume of new, first-time-in-repo wiring across two roots,
not from unresolved design. Both forks that gated the earlier draft (build/
run mechanism; inbound-auth mechanism) are now resolved with citations —
see §11. Node placement remains a live-cluster check, not a blocking fork.

## 3. Triggered by
Operator request to deploy Switchyard, positioned as a routing/protocol-
translation layer in front of the existing Bifrost LLM gateway, scoped to
base deployment + inbound auth only. Hermes's and opencode's cutover onto
Switchyard are explicit non-goals here and become separate tickets under
`epic = "switchyard"` with `depends_on = ["SY1-switchyard-deployment"]`.

## 4. Context

### Bifrost today (what Switchyard sits in front of)
- `deployments/applications/services/bifrost.hcl` (whole file) is the Nomad
  job: `driver = "podman"` (`:18`), image `docker.io/maximhq/bifrost:v${bifrost_version}`
  (`:40`), `governance.auth_config.is_enabled = true` (`:104-108`) and
  `client.enforce_auth_on_inference = true` (`:101`) — every inference
  request needs a valid virtual key. Bifrost load-balances 4 weighted Ollama
  keys and falls back to Gemini (`:110-129`); it does **not** translate
  between Anthropic Messages, OpenAI Responses, and OpenAI Chat. That gap is
  what Switchyard fills.
- `resource "nomad_job" "bifrost"` at `deployments/applications/services.tf:274-302`
  templates the job onto `radxa-dragon-q6a` (192.168.2.50:8080).
- Per-consumer access is a `bifrost_virtual_key.<consumer>` resource
  (`deployments/applications/services.tf:352-361` for `hermes`, `:366-375` for `memex`), each
  `depends_on = [null_resource.bifrost_ready]` (`:315-344`, a `/health`
  poll gate — the Bifrost provider has no built-in retry). The issued
  `.value` is stored in Vault at `default/<consumer>/bifrost` by a
  `vault_kv_secret_v2.bifrost_<consumer>_key` resource
  (`deployments/applications/secrets.tf:85-92` for hermes, `:97-104` for
  memex), read into the consumer's own job by a `vault {}` + `template`
  block (e.g. `deployments/applications/services/hermes.hcl:212,442`).
- No new Vault policy or role is needed to grant a new consumer this KV
  prefix: the shared `nomad-workloads` Vault role auto-grants a workload
  `read` on `secret/data/<nomad_namespace>/<nomad_job_id>/*`, derived purely
  from Workload Identity claims
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-9`).
  R7 already probed this live: `vault policy read nomad-workloads` returned
  exactly that templated path with no `database/` rule
  (`.loop/plans/R7-rollout-postgres-consumer-cutover.md:771-778`, captured
  2026-08-04). A Nomad job literally named `switchyard` therefore reads
  `default/switchyard/*` with zero new Vault policy work — **but only under
  its own KV prefix.** A credential stored anywhere else (e.g.
  `default/minio/switchyard`) is invisible to it; see the MinIO-credential
  bullet below, where this exact trap is why the naming pattern matters.
- `deployments/applications/providers.tf` already configures the `bifrost`
  Terraform provider (`:32-43`) against `null_resource.bifrost_ready`'s
  endpoint, and the `minio` provider (`:10-13` required_providers, `:44-48`
  config block) against Consul-discovered MinIO — no new provider block is
  needed for a new `bifrost_virtual_key` resource or the new MinIO bucket/
  user this ticket adds.

### Switchyard itself (verified against the `main` branch, fetched 2026-08-22)
- Apache-2.0, pre-alpha, current release `v0.2.0` (2026-08-10). Three
  crates matter here: `switchyard-server` (the standalone proxy — what gets
  deployed), `switchyard-libsy` (embeddable, not used here),
  `switchyard launch` (a Python CLI for pointing coding-agent *clients* at
  a server — a consumer-side concern, not this ticket's).
- One explicit TOML deployment file drives it: `schema_version = 1`,
  `[llm_clients.*]` (`format`, `base_url`, `api_key_env`),
  `[targets.*]` (`id`, `llm_client`), `[routes.*]`. Five route `type`s exist:
  `noop`, `random`, `passthrough`, `llm_classifier`, `stage_router`
  (`crates/switchyard-server/README.md`, fetched from `main`). A
  `[routes.passthrough]` entry needs only `type = "passthrough"` and
  `target = "<a targets table key>"`.
- CLI defaults: `--host 0.0.0.0`, `--port 4000`
  (`docs/cli_reference.md`, fetched from `main`). Endpoints:
  `/health`, `/metrics` (Prometheus text), `/v1/stats`, `/v1/models`,
  `/v1/chat/completions`, `/v1/messages`, `/v1/responses`, `/v1/decision`
  (`crates/switchyard-server/README.md`). Documented metric names include
  `switchyard_build_info`, `switchyard_requests_total`,
  `switchyard_errors_total`, `switchyard_model_call_latency_ms`,
  `switchyard_total_latency_ms` (same README, "Metrics" table).
- **Zero inbound authentication, confirmed at the source, not just the
  docs.** The whole HTTP router's middleware stack is exactly a body-size
  cap and a latency-timestamp stamp:
  `.layer(DefaultBodyLimit::max(DEFAULT_MAX_REQUEST_BODY_BYTES))` then
  `.layer(axum::middleware::from_fn(stamp_request_start))`
  (https://github.com/NVIDIA-NeMo/Switchyard/blob/main/crates/switchyard-server/src/lib.rs#L599-L601, `main` branch, fetched 2026-08-22). The
  `CallerAuthKind`/`caller_auth` machinery nearby (`:113-326`) only governs
  which OUTBOUND wire format a `forward_auth = true` client accepts — it is
  not an inbound gate, and this ticket's client does not set
  `forward_auth`. The CLI reference has no `--auth`/`--api-key` flag.
- **No prebuilt artifact exists for the Rust server.** `GET
  /repos/NVIDIA-NeMo/Switchyard/releases` (captured 2026-08-22): the
  `v0.2.0` release has `"assets": []`. Install paths are `cargo install
  --locked switchyard-server --version 0.2.0` (crates.io source) or the
  repo's own `Dockerfile` (root of the repo, `main` branch, re-fetched
  2026-08-22): `ARG RUST_VERSION=1.96.1`, `FROM rust:${RUST_VERSION}-bookworm
  AS builder`, `WORKDIR /opt/switchyard`, `RUN cargo build --locked
  --release -p switchyard-server` (binary lands at
  `/opt/switchyard/target/release/switchyard-server`), then `FROM
  debian:bookworm-slim`, `COPY --from=builder ... /usr/local/bin/switchyard-server`,
  `EXPOSE 4000`, `ENTRYPOINT ["switchyard-server"]` — no `--platform`/
  cross-compile flag anywhere, a native build. `main`'s
  `.github/workflows/publish.yml` publishes Python wheels to PyPI and Rust
  crates to crates.io only; there is no `docker build`/`push` job, so no
  registry image is published either. This ticket uses the `builder` stage
  directly (Requirement 7).

### This repo's deployment conventions
- **Every** existing Nomad task uses `driver = "podman"` pulling a
  prebuilt, versioned image: `grep -rn 'driver = "podman"' deployments/*/services/*.hcl`
  returns 21 hits across every service file in both roots, zero
  counterexamples, and zero uses of `raw_exec` or any build-from-source
  step. Nothing in this repo builds a container image; every job pulls one.
  Switchyard stays `raw_exec` regardless of where the binary is built
  (Open Question A) — no registry, no image, ever, is the constant; only
  *where the compile happens* was in question.
- **No local container registry exists.** A prior ticket's plan wrongly
  assumed one at `firebat:5000`; the plan-validator verdict flagged this as
  a false premise (`.loop/verdicts/R2-rollout-nats-auth-callout.plan-validator.md`).
  Switchyard shipping no upstream image means the podman-driver path this
  repo always uses has nothing to pull from.
- **`raw_exec` is already enabled**, cluster-wide, on every Nomad client
  and server (`bootstrap/roles/nomad_client/templates/nomad.hcl.j2:65-69`,
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:92-96`) — just
  unused by any current job. No Ansible/Nomad-config change is needed to
  turn it on.
- **Nomad's `artifact` and `secret` job-spec blocks have zero prior use in
  this repo.** A naive `grep -rln 'artifact {\|secret "' deployments/`
  returns 52 hits, but every one is a false positive from Consul-Template's
  `{{ with secret "<path>" }}` syntax already used in every job's
  `template` block (e.g. `hermes.hcl:183,188,194,197,200`) — that string
  contains `secret "` without being the Nomad `secret {}` block this
  ticket introduces. A pattern anchored to real block syntax
  (`^\s*artifact\s*{` or `^\s*secret\s*"[a-zA-Z_]*"\s*{`) returns zero
  hits, re-verified 2026-08-22 (Premise P17). This ticket is the first
  real use of both — see Open Question A's resolution and Premises
  P12-P14 for why they are still the correct mechanism, not merely the
  only one tried.
- **Node placement, current state, re-verified 2026-08-22** (parsed each
  service file's own `constraint { attribute = "$${attr.unique.hostname}" }`
  value, cross-referencing template vars against `services.tf` where the
  constraint itself is templated):
  - `firebat` (192.168.2.30): `haproxy`, `postgres` — 2 jobs. Postgres alone
    reserves `cpu = 2000, memory = 6144` (`deployments/infrastructure/services/postgres.hcl:82-85`)
    plus its exporter (`cpu = 200, memory = 64`, `:150-153`); haproxy adds
    `cpu = 500, memory = 128` (`deployments/infrastructure/services/haproxy.hcl:180-183`).
    **Combined Nomad-reserved memory ≈ 6.3 GB already**, on a board whose
    total RAM this repo does not record anywhere.
  - `radxa-dragon-q6a` (192.168.2.50): `bifrost`, `hermes`, `redis`, `nats`,
    `backup-postgres`, `backup-minio`, **and now `oauth2-proxy`** (L1
    shipped since this ticket's first draft — Premise P2) — 7 jobs, the
    busiest node.
  - `orangepi4a` (192.168.2.29): `phoenix` **and `minio`** — 2 jobs (the
    ticket's first draft undercounted this node at 1).
  - `jetson-orin-nano` (192.168.2.46): `memex` — 1 job, reserving only
    `cpu = 500, memory = 512` (`deployments/applications/services/memex.hcl:62-65`).
    **This is now the lightest node by both job count and reserved memory**,
    and its architecture is unambiguous (an NVIDIA Jetson board is ARM by
    hardware identity, not inferred).
  - `ubuntu` / raspberry_pi_4b (192.168.2.47): `grafana`, `loki`, `acme`,
    `prometheus` — 4 jobs.
  - `promtail`, `node-exporter` are unconstrained system jobs (run on every
    node) and are excluded from these counts, matching the rest of this
    section's own methodology.
  `docs/monitoring.md:261` claims firebat has "the most headroom" but that
  claim is self-flagged historical by the same document
  (`docs/monitoring.md:250-253`: "predates the move of Prometheus and
  Grafana from firebat to `ubuntu`") — current placement moved Prometheus
  and Grafana OFF firebat, so that headroom number cannot be trusted as
  live. **Job count and reserved memory alone no longer favor firebat**
  (2 jobs, tied with orangepi4a) **over jetson-orin-nano** (1 job) — but
  live headroom data gathered this revision (Premise P10) overturns the
  reservation-based case entirely: `jetson-orin-nano` is memory-critical
  in practice, `radxa` is not. See Open Question A's updated
  recommendation.
- **Node CPU architecture, live-verified this revision for 3 of 5 nodes
  (Premise P10, corrected — network access to the cluster IS available;
  Premise P9, corrected).** `jetson_nano`, `raspberry_pi_4b`, and `radxa`
  are all confirmed `aarch64` by direct `ssh ... uname -m`. `firebat` and
  `orange_pi_4a` remain unverified — not because of a routing gap, but
  because SSH to both refused with a host-key mismatch (Premise P9a),
  which this session did not bypass. See Premise P10 for the full live
  data (headroom included) and Open Question A for the resulting
  node-placement change.
- **Inbound auth for a service with none of its own: one proven mechanism,
  and it is a reverse-proxy gate, not forward-auth.**
  - **L1-landing-oauth2-proxy is `done`** (`loopctl ledger | grep L1`,
    re-verified 2026-08-22; landed in commit `e48742e`,
    "L1-landing-oauth2-proxy: deploy oauth2-proxy as the landing-page OIDC
    gate"). The ticket's first draft cited a stale 2026-08-22 ledger
    snapshot showing L1 `blocked` — corrected here; see Premise P2. R1
    (MLflow) and R4 (Phoenix) remain `blocked`, but for reasons specific to
    their own backends, not the oauth2-proxy mechanism: R1's verdict cites
    a closed-`not_planned` MLflow GitHub issue and notes MLflow now ships
    its own SSO plugin (`.loop/verdicts/R1-rollout-mlflow-oauth2-proxy.plan-validator.md`);
    R4's verdict cites Phoenix hard-requiring an email claim that Vault's
    ID token does not emit
    (`.loop/verdicts/R4-rollout-phoenix-oauth2-proxy.plan-validator.md`).
    Neither blocker is about oauth2-proxy itself. **The mechanism is proven
    and live in this repo; its two follow-on reuse attempts failed on
    backend-specific integration gaps, not on the gate.**
  - **The live mechanism is a reverse proxy, not a forward-auth sidecar.**
    `deployments/infrastructure/services/haproxy.hcl`'s `backend dash`
    (`:155-156`) points directly at oauth2-proxy's own port
    (`192.168.2.50:4180`) — there is no separate "dash" application behind
    it. oauth2-proxy IS the origin server HAProxy proxies to: its own job
    sets `OAUTH2_PROXY_UPSTREAMS="static://200"`
    (`deployments/infrastructure/services/oauth2-proxy.hcl:54`), so an
    authenticated request simply gets a static 200 from oauth2-proxy
    itself. There is no `auth-request`/`auth_request` directive anywhere in
    `haproxy.hcl` (`grep -n 'auth_request\|auth-request'
    deployments/infrastructure/services/haproxy.hcl`: zero hits, verified
    2026-08-22) — HAProxy never asks a separate service "is this request
    allowed" and then proxies elsewhere on approval; it proxies straight
    through oauth2-proxy, which fronts the real origin (Premise P16).
  - **Today's oauth2-proxy is one job for one consumer, and its config is
    hardcoded, not templated, for the piece that matters here.** The
    job's own header comment says "Reusable pattern: R1 (MLflow) and R4
    (Phoenix) copy this job" (`oauth2-proxy.hcl:6-8`) — but the
    `templatefile()` call that renders it
    (`deployments/infrastructure/services.tf:400-409`, `resource
    "nomad_job" "oauth2_proxy"`) only threads three vars: `oidc_secret`,
    `cookie_secret`, `redirect_url`. `OAUTH2_PROXY_UPSTREAMS` and the
    static port `4180` are literal values in the job body
    (`oauth2-proxy.hcl:35,54`), not template vars — "copy this job" means a
    near-duplicate file per consumer, not a parameterized shared job. R1
    and R4's own (still-`blocked`, unimplemented) plans already assumed
    this shape: R1's plan text says "CREATE an oauth2-proxy Nomad task/job
    — either a new task inside `mlflow.hcl` ... or a separate `*.hcl` job"
    (`.loop/plans/R1-rollout-mlflow-oauth2-proxy.md:182-188`).
  - Reused pieces: `resource "vault_identity_oidc_client" "oauth2_proxy"`
    (`deployments/infrastructure/oidc.tf:168-179`) +
    `vault_identity_oidc_key_allowed_client_id.oauth2_proxy`
    (`:183-187`), the `locals.oauth2_proxy_redirect_url` just above it
    (`:164-166`), and the **`>>> CONSUMER TICKETS: APPEND YOUR CLIENT
    HERE <<<`** line the file itself calls out: `local.oidc_provider_client_ids`
    (`oidc.tf:79-85`) is the one list every new OIDC client must append its
    `client_id` to, or Vault refuses the authorization request against the
    provider (`oidc.tf:69-73`'s own comment). The Vault KV secret pattern
    to mirror is `vault_kv_secret_v2.oauth2_proxy_oidc_client`
    (`deployments/infrastructure/secrets.tf:186-199`) and
    `random_password.oauth2_proxy_cookie_secret` /
    `vault_kv_secret_v2.oauth2_proxy_cookie_secret` (`:207-210`, `:212-224`).

### How a Vault-issued MinIO credential reaches a static Nomad jobspec value
(new research this revision, resolving Open Question A's "how does Nomad
fetch it" sub-question — see §11 for the design, this bullet for the
evidence)
- Nomad's `artifact` stanza's `options` map is documented as "specifies
  configuration parameters to fetch the artifact... key-value pairs map
  directly to parameters appended to the supplied source URL"
  (developer.hashicorp.com/nomad/docs/job-specification/artifact, fetched
  2026-08-22) — a static jobspec value, unlike `template`, which re-renders
  at runtime from a `vault {}`-derived token. `ephemeral` Terraform
  resources (this repo's stated preference for reading a secret's VALUE,
  not just its path — see Premise P15) explicitly "cannot flow into
  templatefile's non-write-only vars map"
  (`deployments/infrastructure/acme.tf:95-98`, this repo's own words).
- Nomad ships a purpose-built answer: the `secret` job-spec block, added in
  Nomad 1.11.0 ("secrets: Adds secret block for fetching and interpolating
  secrets in job spec", GH-26681,
  raw.githubusercontent.com/hashicorp/nomad/main/CHANGELOG.md, fetched
  2026-08-22). This cluster pins Nomad `2.0.4-1`
  (`bootstrap/inventory/group_vars/all.yml:12`), newer than 1.11.0, so the
  block is available. Its `vault` provider builds the *exact same*
  `{{ with secret "<path>" }}` Consul-Template string the `template` stanza
  already uses in every job in this repo, off the *same* task-level
  `vault {}` token
  (`client/allocrunner/taskrunner/secrets/vault_provider.go`, `hashicorp/
  nomad` `main` branch, fetched 2026-08-22) — so it inherits the identical
  zero-new-policy grant this ticket already relies on for the Bifrost key
  (Requirement 7, Premise P13). The artifact doc's own example shows the
  interpolation landing directly inside `artifact.options`:
  `aws_access_key_id = "${secret.aws.key_id}"` (same doc page, fetched
  2026-08-22).
- The alternative the request explicitly asked to be checked — a public-
  read MinIO bucket needing no credentials at all — does not actually
  avoid the credential problem. go-getter's own S3-getter docs state
  plainly, under "Using S3 with Minio": "`aws_access_key_id` (required) —
  Minio access key. `aws_access_key_secret` (required)"
  (raw.githubusercontent.com/hashicorp/go-getter/main/README.md, fetched
  2026-08-22) — unlike plain AWS S3, which can fall back to an IAM
  instance profile, go-getter's Minio path has no anonymous-request mode.
  Reading `get_s3.go`'s `getAWSConfig` confirms this in code: when no
  static credentials are supplied, it does not set `aws.AnonymousCredentials`;
  it falls through to the AWS SDK's default credential chain, which on a
  non-EC2 host with no AWS env vars configured has nothing to resolve and
  the signed S3 call fails regardless of the bucket's own anonymous-read
  policy (Premise P12). MinIO's own Terraform provider does support a real
  `acl = "public-read"` bucket policy (`resource_minio_s3_bucket.go`'s
  `defaultPolicies` map and `SetBucketPolicy` call, `aminueza/
  terraform-provider-minio` `main` branch, fetched 2026-08-22) — the object
  itself would be anonymously GET-able over plain HTTP — but go-getter
  never attempts an unauthenticated request to find out. **Public-read does
  not solve this; the native `secret` block does**, and does it without
  putting the credential in Terraform state (unlike the repo's one other
  precedent for a Vault-value-in-state, `data.vault_kv_secret_v2.bifrost_admin`
  at `deployments/infrastructure/secrets.tf:124`, kept there only because
  its consumer is a persisted `vault_kv_secret_v2` resource, not a
  jobspec).
- **The credential's Vault path still has to live under the job's own KV
  prefix**, not under the generic `default/minio/<name>` path the repo's
  bulk MinIO-credential resource writes to
  (`vault_kv_secret_v2.minio_credentials`, `for_each = minio_accesskey.users`,
  `deployments/applications/secrets.tf:117-124`). Neither `memex` nor
  `loki` — the two live MinIO-backed Nomad jobs — read from that generic
  path: each has its own explicitly-named resource under its own job-id
  prefix instead (`vault_kv_secret_v2.memex_minio_credentials` at
  `default/memex/minio`, `deployments/applications/secrets.tf:31-38`; `vault_kv_secret_v2.loki_minio_credentials`
  at `default/loki/minio`, `:42-48`), because that is the only path their
  `nomad-workloads` grant actually covers. Switchyard's MinIO reader
  credential needs the same treatment (Premise P15, Code surface item 3).
- Whatever go-getter writes to disk is **not executable**:
  `S3Getter.getObject` writes with `copyReader(dst, body, 0666, ...)`
  (go-getter's `get_s3.go` line 211,
  raw.githubusercontent.com/hashicorp/go-getter/main/get_s3.go, fetched
  2026-08-22) — mode 0666, no execute bit. The
  `artifact` block itself has no `perms` parameter (only `chown`, a
  boolean). The `raw_exec` task's own command must `chmod +x` the fetched
  binary before exec'ing it (Premise P14, Code surface item 1).

## 5. Non-goals / out of scope
- **Hermes cutover.** Routing Hermes's LLM calls through Switchyard instead
  of directly at Bifrost. Hermes's Bifrost provider wiring
  (`deployments/applications/services/hermes.hcl:112-232,442`) is untouched
  by this ticket. Separate follow-on ticket, `depends_on =
  ["SY1-switchyard-deployment"]`.
- **opencode cutover.** `opencode` is not referenced anywhere in this repo
  today (`grep -rli opencode deployments docs` — no hits); a follow-on
  ticket has to establish that surface before it can cut over to
  Switchyard. Also `depends_on = ["SY1-switchyard-deployment"]`.
- **Authenticating a headless/API caller through the edge gate.** oauth2-
  proxy's session is a human browser OIDC login (cookie-based); it does not
  by itself authenticate a machine client sending its own bearer token.
  Fine here — this ticket's only caller is a human verifying the
  deployment, and Non-goals already excludes Hermes/opencode as consumers
  — but a follow-on cutover ticket inherits this gap. See Open Question B's
  resolution for the concrete (non-blocking) mechanism that ticket will
  need.
- **Multi-tier/classifier routing** (`llm_classifier`, `stage_router`,
  `escalation`, weighted `random`). Day one has exactly one upstream
  (Bifrost), so `passthrough` is the only route type configured. Bifrost
  already does its own weighted load-balancing across 4 Ollama keys
  (`bifrost.hcl:112-117`); nothing here needs a second, judge-selected
  tier yet. If a later need for tiering appears, it is scoped once there
  is a second, materially different upstream to route between.
- **Bifrost's own config.** No change to `bifrost.hcl` or its embedded
  `config.json` beyond registering one new virtual-key consumer.
  `governance.auth_config` / `client.enforce_auth_on_inference` stay as-is.
- **LAN-wide firewalling of Switchyard's raw Nomad port.** Bifrost has the
  identical gap today — no `firewall_rules` entry restricts direct access
  to `192.168.2.50:8080`. `N4-netsec-edge-only-service-access` (still
  `planning`) owns closing this cluster-wide; this ticket does not
  duplicate that work for one more service.
- **A shared local container registry, or any general-purpose build/publish
  pipeline.** The MinIO bucket this ticket adds (`switchyard-artifacts`) is
  scoped to exactly one binary, uploaded once by hand; it is not reusable
  infrastructure for other services' builds.
- **Publishing a distributable Switchyard image or binary for anyone else
  to pull.** The new bucket stays private; only the `switchyard` MinIO
  identity (read-only) and the existing MinIO admin credential (for the
  one-time upload) can reach it.
- **A build/publish script or CI job.** The off-cluster build is a
  documented, one-time manual command sequence (§8), not a new script or
  pipeline — matching this repo's no-CI-on-infra convention (§8's own
  "Repo gate" note) and its stated additive-only discipline (this
  section's other entries).
- **New `docs/` pages.** This ticket's own prose is the documentation for
  the base deployment; no `docs/switchyard.md` is added here.

## 6. Requirements & restrictions
1. New Nomad job named exactly `switchyard` (the literal string matters —
   it is what makes the shared `nomad-workloads` Vault policy grant
   `default/switchyard/*`; see Context and
   `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-9`).
   One `nomad_job` Terraform resource in
   `deployments/applications/services.tf`, templating a new
   `deployments/applications/services/switchyard.hcl`, shaped like the
   existing `bifrost.hcl` (network/service/check/`vault{}`/template/
   resources blocks).
2. One TOML deployment (`schema_version = 1`) with a single
   `[llm_clients.bifrost]` block (`format = "openai_chat"`, `base_url`
   pointed at Bifrost's LAN address `192.168.2.50:8080`, `api_key_env`
   naming an env var) and a single `[routes.passthrough]` block
   (`type = "passthrough"`, `target` referencing that client's
   `[targets.*]` entry) — matching the shape documented in
   `crates/switchyard-server/README.md`'s `routes.toml` example. No
   `forward_auth` on this client (Requirement 3 supplies its own key).
3. `api_key_env` resolves to a NEW `bifrost_virtual_key.switchyard`
   resource (mirror `bifrost_virtual_key.hermes`,
   `deployments/applications/services.tf:352-361`), whose `.value` is
   stored in Vault at `default/switchyard/bifrost` by a new
   `vault_kv_secret_v2.bifrost_switchyard_key` resource (mirror
   `vault_kv_secret_v2.bifrost_hermes_key`,
   `deployments/applications/secrets.tf:85-92`), `depends_on =
   [null_resource.bifrost_ready]`.
4. `/metrics` needs no auth wiring to be scraped: tag the job's `service`
   stanza `"prometheus"` (mirror `deployments/infrastructure/services/postgres.hcl:102`,
   `deployments/infrastructure/services/nats.hcl:109`) so the existing `consul_services` Prometheus job
   (`deployments/infrastructure/services/prometheus.hcl:155-169`)
   auto-discovers it. No edit to `prometheus.hcl` itself.
5. A Grafana dashboard is provisioned, mirroring Bifrost's exact wiring: a
   new `deployments/infrastructure/services/grafana/switchyard.json`, a
   new `switchyard_dashboard = file(...)` local added to the
   `nomad_job.grafana` `templatefile()` call
   (`deployments/infrastructure/services.tf:368-390`, alongside
   `bifrost_dashboard` at `:382`), and a new `template` block in
   `deployments/infrastructure/services/grafana.hcl` (mirror `:218-226`).
   Panels built from Switchyard's documented metric names (Context).
6. **RESOLVED (Open Question B, operator-selected 2026-08-22 — reuse
   oauth2-proxy).** Edge access at `switchyard.lab.orangecluster.nl` is
   gated by a **second, Switchyard-scoped oauth2-proxy Nomad job**
   (`oauth2-proxy-switchyard`), a near-duplicate of L1's already-`done`
   job, not a new HAProxy-native mechanism. Its own `OAUTH2_PROXY_UPSTREAMS`
   points at Switchyard's own address (co-located on the same node, over
   `127.0.0.1:4000`) instead of L1's placeholder `static://200`.
   `deployments/infrastructure/services/haproxy.hcl`'s new `backend
   switchyard` points at THIS NEW oauth2-proxy instance's address, exactly
   as `backend dash` points at L1's oauth2-proxy (`:155-156`) — never at
   Switchyard's own port directly. HAProxy itself holds no Switchyard-
   specific secret: no new `random_password`/`vault_kv_secret_v2` edge
   credential is threaded into `haproxy.hcl`'s own job wiring, unlike the
   ticket's first-draft Bearer-ACL design (B1). This ships a working
   human-browser OIDC gate; it does not authenticate a headless API caller
   (Non-goals, Risk assessment).
7. **RESOLVED (Open Question A, operator-selected 2026-08-22 — build off-
   cluster, publish, fetch).** `switchyard-server` is built off-cluster
   (the repo's own `Dockerfile`'s `builder` stage, run standalone — exact
   command in §8), targeting a node that is BOTH the same CPU
   architecture (aarch64) AND has the LSE atomics Switchyard's own
   `.cargo/config.toml` requires for aarch64 (`target-cpu=neoverse-n1`;
   Premise P18) — confirmed live before building for both properties, not
   assumed for either. `radxa` and `jetson-orin-nano` qualify;
   `raspberry_pi_4b` does NOT (Open Question A). The
   binary is uploaded once, by hand, to a new private MinIO bucket
   (`switchyard-artifacts`) using the existing MinIO admin credential
   (`default/minio/localstack`) — no new writer identity. The deployed
   job (`driver = "raw_exec"`; still no image/registry exists) fetches it
   at task-start via Nomad's `artifact` stanza
   (`s3::http://<minio-host>:9000/switchyard-artifacts/<key>`), with
   credentials supplied by a first-in-repo `secret { provider = "vault" }`
   block reading a dedicated, read-only `switchyard` MinIO identity's key
   from Vault and interpolating it into `artifact.options` — not a
   `template` block (cannot populate a static jobspec value; Context) and
   not a public/anonymous bucket (go-getter's S3 getter requires explicit
   credentials for MinIO regardless of the bucket's own ACL; Context,
   Premise P12). The fetched binary is not executable by default (mode
   0666; Premise P14) — the `raw_exec` command chmods it before exec.
8. Whichever mechanism builds/runs `switchyard-server`, and whichever
   mechanism gates the edge, must not require a new Vault policy or a new
   Terraform provider block, and must not edit another job's existing
   config. Verified for both resolutions above: the `secret {}` block
   reuses the existing `nomad-workloads` grant (zero new policy); the
   `minio` and `vault` Terraform providers already exist in both roots
   (`deployments/applications/providers.tf:10-13,44-48`); no existing
   `.hcl`/`.tf` file's current resources are edited, only new ones added
   (Code surface).
9. Terraform providers pinned at `deployments/applications/providers.tf:1-30`;
   no version bump.
10. `.claude/rules/adversarial-reviews.md` — dispatch an adversarial
    sub-agent review before declaring this done.
11. `.claude/rules/prek-code-quality.md` — run gates through `just`/`prek`,
    never the bare `terraform`/`nomad` binaries directly, so the pinned
    invocation is used.
12. Match existing HCL/Terraform naming and comment style; no unrelated
    refactors of files this ticket touches (`CLAUDE.md`, "Surgical
    Changes").

## 7. Code surface

### `deployments/applications` root
1. `deployments/applications/services/switchyard.hcl` **(new)** — Nomad
   job. `driver = "raw_exec"`; `network { port "http" { static = 4000 } }`;
   `service { name = "switchyard" tags = ["http", "llm", "prometheus"] }` +
   `check` on `/health`; `vault {}`; a `secret "minio" { provider = "vault"
   path = "<var>" config { engine = "kv_v2" } }` block (Requirement 7); a
   `template` rendering `local/routes.toml` per Requirement 2; a `template`
   rendering the Bifrost API-key env var (pattern: `bifrost.hcl:60-89`); an
   `artifact { source = "s3::http://<minio_host>:9000/switchyard-artifacts/<key>"
   destination = "local/switchyard-server" mode = "file" options {
   aws_access_key_id = "${secret.minio.access_key}" aws_access_key_secret =
   "${secret.minio.secret_key}" region = "us-east-1" } }`; `config { command
   = "/bin/sh" args = ["-c", "chmod +x local/switchyard-server && exec
   local/switchyard-server --config local/routes.toml"] }`; `resources {}`.
   Node `constraint` per Open Question A's updated recommendation, pending
   live verification.
2. `deployments/applications/storage.tf:2-33` (`locals.buckets`) — add a
   new bucket entry: `"switchyard-artifacts" = { writers = [], readers =
   [{ "name" = "switchyard", generate_access_key = true }] }`. Free-rides
   the existing `for_each` machinery with zero new resource types:
   `local.all_minio_users`/`local.access_key_users` (`:35-47`),
   `minio_iam_user.users["switchyard"]`/`minio_accesskey.users["switchyard"]`
   (`:50-59`), and `module.buckets["switchyard-artifacts"]` (`:61-72`),
   which grants `switchyard` the module's `policy_read_only` IAM policy
   (`deployments/applications/modules/bucket/main.tf:29-58`). Bucket `acl`
   stays the module's `private` default (no `var.acl` override) — the
   `secret {}` block, not bucket anonymity, is what makes the fetch work
   (Context).
3. `deployments/applications/secrets.tf:31-38` (pattern:
   `memex_minio_credentials`) — new `resource "vault_kv_secret_v2"
   "switchyard_minio_credentials"` at `default/switchyard/minio`, sourcing
   `minio_accesskey.users["switchyard"].access_key`/`.secret_key`. Must be
   this explicitly-named, job-prefixed resource, NOT the generic `for_each`
   `vault_kv_secret_v2.minio_credentials` at `default/minio/switchyard`
   (`:117-124`) — that path is outside the `nomad-workloads` grant for a
   job named `switchyard` (Context).
4. `deployments/applications/services.tf:274-302` (pattern) — add
   `resource "nomad_job" "switchyard"` near `nomad_job.bifrost`,
   `depends_on = [vault_kv_secret_v2.bifrost_switchyard_key,
   vault_kv_secret_v2.switchyard_minio_credentials]`.
5. `deployments/applications/services.tf:352-361` (pattern) — add
   `resource "bifrost_virtual_key" "switchyard"`.
6. `deployments/applications/secrets.tf:85-92` (pattern) — add `resource
   "vault_kv_secret_v2" "bifrost_switchyard_key"` at
   `default/switchyard/bifrost`.

### `deployments/infrastructure` root
7. `deployments/infrastructure/services/oauth2-proxy-switchyard.hcl`
   **(new)** — near-duplicate of `oauth2-proxy.hcl` (whole file, pattern).
   Differences from the source file: job name `oauth2-proxy-switchyard`;
   `OAUTH2_PROXY_UPSTREAMS="http://127.0.0.1:4000"` (`:54` in the source)
   instead of `static://200`; `network { port "http" { static = 4181 } }`
   (`:35` in the source) instead of `4180`, to avoid colliding with L1's
   live instance; `constraint` hostname matching whatever node Switchyard
   itself lands on (co-located, `network_mode = "host"`, so the loopback
   upstream resolves). Every other line (issuer/client/cookie template
   vars, `EMAIL_DOMAINS=*`, `OIDC_EMAIL_CLAIM=sub`,
   `SKIP_PROVIDER_BUTTON=false`, the `/ping` health check, the image
   pin) is unchanged from the source file.
8. `deployments/infrastructure/oidc.tf:164-166,168-179,183-187` (pattern)
   — new `locals.oauth2_proxy_switchyard_redirect_url =
   "https://switchyard.lab.orangecluster.nl/oauth2/callback"`, new
   `resource "vault_identity_oidc_client" "oauth2_proxy_switchyard"`, new
   `resource "vault_identity_oidc_key_allowed_client_id"
   "oauth2_proxy_switchyard"`.
9. `deployments/infrastructure/oidc.tf:79-86` (`locals.oidc_provider_client_ids`)
   — append `vault_identity_oidc_client.oauth2_proxy_switchyard.client_id`
   to the list. Per the file's own marked instruction (`:69-73`): omitting
   this makes Vault refuse the authorization request outright.
10. `deployments/infrastructure/secrets.tf:186-199,207-210,212-224`
    (pattern) — new `vault_kv_secret_v2.oauth2_proxy_switchyard_oidc_client`
    at `default/oauth2-proxy-switchyard/oidc`, new
    `random_password.oauth2_proxy_switchyard_cookie_secret` (`length = 32,
    special = false`, matching the source's own comment about
    base64url-decoded byte length), new
    `vault_kv_secret_v2.oauth2_proxy_switchyard_cookie_secret` at
    `default/oauth2-proxy-switchyard/cookie`.
11. `deployments/infrastructure/services.tf:398-409` (pattern:
    `resource "nomad_job" "oauth2_proxy"`) — new `resource "nomad_job"
    "oauth2_proxy_switchyard"`, `jobspec = templatefile(".../
    oauth2-proxy-switchyard.hcl", { oidc_secret = ..., cookie_secret =
    ..., redirect_url = local.oauth2_proxy_switchyard_redirect_url })`.
12. `deployments/infrastructure/services/haproxy.hcl:98-118,155-156` — add
    `acl is_switchyard hdr(host) -i switchyard.lab.orangecluster.nl`,
    `use_backend switchyard if is_switchyard`, and `backend switchyard {
    server switchyard1 <node-ip>:4181 check }` — pointing at the NEW
    oauth2-proxy-switchyard instance's port, mirroring `backend dash`
    exactly (`:155-156`), not at Switchyard's own `:4000`.
13. `deployments/infrastructure/services/grafana.hcl:218-226` (pattern) —
    new `template` block, `destination = "local/dashboards/switchyard.json"`.
14. `deployments/infrastructure/services/grafana/switchyard.json` **(new)**
    — dashboard JSON; pattern file `deployments/infrastructure/services/grafana/bifrost.json`.
15. `deployments/infrastructure/services.tf:368-390` (`nomad_job.grafana`
    resource, re-verified post-L1: line numbers shifted +8 from the
    ticket's first draft) — add `switchyard_dashboard =
    file("${path.module}/services/grafana/switchyard.json")` to the
    `templatefile()` call, alongside `bifrost_dashboard` at `:382`.

**No code-surface item exists for the one-time build+publish step** — it
is a documented manual command sequence (§8, Requirement 7's own text),
not a repo file. It requires `podman` and either `mc` (MinIO client) or
`aws s3 --endpoint-url=...` on the operator's own workstation; neither is
currently a repo dependency, and adding neither is in scope here (Non-goals).

## 8. Tests & validation gates

### Repo gate
- **Command:** `just pre_commit` → all Passed. Runs `nomad fmt -recursive`
  (formats every new/edited `.hcl` file), `terraform fmt -check -recursive`,
  `terraform validate` on every root per `scripts/tf_validate.sh:8-11`
  (`deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`), and the generic
  `pre-commit-hooks` (json/yaml/merge-conflict/private-key/EOF) —
  `.pre-commit-config.yaml`. The `cli/`-scoped hooks (ruff, mypy, pytest)
  do not apply; this ticket touches no Python.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:44-47`)
  — copies only the infrastructure root's `prod.tfvars` by the recipe's own
  comment, so also copy `deployments/applications/vars/prod.tfvars` (or
  the equivalent) by hand before validating the applications root, or
  `terraform validate` there fails on missing vars.

### Off-cluster build + one-time publish (Requirement 7)
Run once, by hand, before the `switchyard` Nomad job is first applied.
`<arch>` is whatever the chosen run node's live `uname -m` reports — for
the recommended node (`radxa`), this is now confirmed `aarch64` by a live
probe, not a guess (Premise P10). The commands below assume
`arm64`/`aarch64` accordingly; re-confirm with `ssh radxa uname -m`
immediately before building regardless (live state can drift), and swap
to `amd64`/`x86_64` if a different node is chosen instead. **If a
DIFFERENT node than `radxa`/`jetson-orin-nano` is ever substituted, also
run `ssh <node> "grep -m1 Features /proc/cpuinfo | grep -o atomics"`
before building — matching `arm64`/`aarch64` alone is not enough
(Premise P18): Switchyard's default aarch64 build requires LSE atomics,
which `raspberry_pi_4b` (Cortex-A72) does not have and would silently
`SIGILL` at runtime despite a clean build and a matching `uname -m`.**
```
git clone --depth 1 --branch v0.2.0 https://github.com/NVIDIA-NeMo/Switchyard.git
cd Switchyard
podman build --platform linux/arm64 --target builder -t switchyard-build:v0.2.0 .
podman create --name switchyard-extract switchyard-build:v0.2.0
podman cp switchyard-extract:/opt/switchyard/target/release/switchyard-server \
  ./switchyard-server-v0.2.0-aarch64
podman rm switchyard-extract

vault kv get -mount=secret default/minio/localstack   # read the admin access_key/secret_key
mc alias set switchyard-admin http://<minio-lan-ip>:9000 minio <secret_key-from-above>
mc cp ./switchyard-server-v0.2.0-aarch64 \
  switchyard-admin/switchyard-artifacts/switchyard-server-v0.2.0-aarch64
```
Offline sanity before uploading: `./switchyard-server-v0.2.0-aarch64 --config
routes.toml --dry-run` on a matching-architecture host (or under an
`--platform`-matched container) — checks schema, env-var lookups, and
target references without binding a socket.

### Offline checks before applying
- `terraform -chdir=deployments/applications validate` and `terraform
  -chdir=deployments/infrastructure validate` (offline, no credentials)
  must pass. `terraform plan`/`apply` need live Vault/Nomad/Consul
  **credentials** this authoring session does not have — network
  reachability is NOT the blocker (Premise P9, corrected: Consul and
  Bifrost respond, SSH succeeds to 3 of 5 nodes); the missing piece is a
  Vault token and a Nomad ACL token (Nomad's API returned a genuine `403`
  to an unauthenticated request, captured 2026-08-22 — an auth rejection,
  not a routing failure). Whoever implements this ticket with real
  Vault/Nomad credentials runs `plan`/`apply` and the live evals below.

### Live evals (need real cluster access — authoritative set:
`.loop/evals/SY1-switchyard-deployment.md`, recommended next per
`create-ticket`'s "After the ticket: ask about the eval" section)
- `curl -fsS http://<switchyard-node-ip>:4000/health` → 200 (pre-edge
  sanity, direct to the job).
- The first alloc's Nomad task events show the `artifact` download
  completing (source resolved, no `secret.minio.*` interpolation error)
  and the `raw_exec` command's `chmod +x` + exec succeeding — this repo's
  first live exercise of both the `artifact` and `secret` job-spec
  mechanisms (Context, Risk assessment).
- `curl -fsS https://switchyard.lab.orangecluster.nl/v1/models` with NO
  credential → redirected to oauth2-proxy's login page, not a direct 401/
  403 passthrough (the gate is a browser OIDC redirect, not a static
  Bearer-ACL check — matches L1's own proven shape, not the ticket's
  first-draft Bearer-ACL design).
- A completed browser OIDC login against `switchyard.lab.orangecluster.nl`
  reaches Switchyard's `/v1/models` and lists the `switchyard`-id
  passthrough route.
- `POST https://switchyard.lab.orangecluster.nl/v1/chat/completions`
  (post-login session, trivial prompt) → 200; the SAME logical request via
  `/v1/messages` (Anthropic shape) → 200 with an Anthropic-shaped response
  (proves translation is live, not just proxying one wire format).
- Prometheus shows `up{job="switchyard"}` (via `consul_services` SD, tag
  `"prometheus"`) == 1 within one scrape interval.
- The new Grafana dashboard renders non-zero `switchyard_requests_total`
  after the smoke calls above.

No repo-native unit-test harness exists for Terraform/Nomad HCL (this repo
has no CI on infra changes — matches
`.loop/plans/T5-tls-certificate-expiry-alert.md:124-125`'s own statement),
so the eval file above is the authoritative Definition of Done, not a
pytest suite.

## 9. Risk assessment
- **Blast radius:** additive throughout — new Nomad jobs (switchyard,
  oauth2-proxy-switchyard), a new HAProxy backend, a new MinIO bucket/user,
  new Vault OIDC client/secrets. Nothing existing is edited except three
  append-only insertion points: `oidc.tf`'s `local.oidc_provider_client_ids`
  list, `services.tf`'s two `templatefile()` calls (grafana dashboard,
  each root's job list), and `haproxy.hcl`'s ACL/backend list. No existing
  job's own resource body changes.
- **Reversibility:** high on the Terraform side — remove the resources,
  `terraform apply` tears the jobs/routes/secrets/bucket down cleanly.
- **Failure mode 1 — this repo's first live use of Nomad's `artifact` and
  `secret` job-spec stanzas.** Both are documented, stable, non-experimental
  Nomad features (Context), but neither has run against this specific
  cluster before. Concrete new risk this design introduces versus the
  ticket's first-draft "compile on the target node" approach: the off-
  cluster build MUST target BOTH the exact CPU architecture AND the CPU
  feature set of whichever node ultimately runs the job, confirmed live,
  or the fetched binary simply fails to exec — a mismatch this repo would
  previously have caught for free (on-node compilation always matches the
  node it runs on). It is not enough to match `aarch64`: Switchyard's
  default aarch64 build targets Neoverse-N1-class LSE atomics
  (`.cargo/config.toml`, Premise P18), which `radxa` and
  `jetson-orin-nano` have and `raspberry_pi_4b` (Cortex-A72) does not — a
  `SIGILL`, not a graceful failure. §8's build commands assume
  `arm64`/`aarch64` WITH LSE, now confirmed live for the recommended node
  (`radxa`, Premises P10/P18) rather than inferred — the residual risk is
  DRIFT (re-check immediately before building; live state can change) and
  choosing a fallback node without re-checking BOTH properties, not the
  original architecture-unknown gap.
- **Failure mode 2 — build reproducibility.** The build is a documented
  manual command, not a script (Non-goals, deliberately, per this repo's
  no-speculative-infra convention). A future version bump or a lost build
  host means re-deriving the exact command from this ticket's own text
  (§8) rather than re-running a checked-in script. Low likelihood of
  breakage, but a real, accepted tradeoff of the "smaller surface" choice.
- **Failure mode 3 — the second oauth2-proxy instance's port/upstream
  drifts from Switchyard's own node/port.** Both `oauth2-proxy-switchyard`'s
  `constraint` and `OAUTH2_PROXY_UPSTREAMS` are hand-set to match wherever
  Switchyard itself is placed. If Switchyard's node constraint changes
  later without a matching edit to the oauth2-proxy-switchyard job, the
  gate still accepts logins but proxies to a dead or wrong upstream —
  a silent 502 behind a working-looking login page, not an obvious failure.
- **Failure mode 4 — inbound-auth mechanism does not authenticate a
  headless caller.** oauth2-proxy's session is a browser OIDC cookie flow.
  A future Hermes/opencode consumer (out of THIS ticket's scope, but the
  reason this auth mechanism exists) will send its own Bearer/`x-api-key`
  credential as an OpenAI/Anthropic-shaped client, which this gate does not
  understand. Because this ticket's `[llm_clients.bifrost]` uses
  `api_key_env` (not `forward_auth`), Switchyard itself never reads or
  needs the caller's Authorization header, so this ticket ships a complete,
  working gate for its own (human-verification) purposes — but a follow-on
  cutover ticket needs its own mechanism. **Non-blocking note for that
  future ticket:** oauth2-proxy supports a bearer-JWT skip mode
  (`--skip-jwt-bearer-tokens` + `--extra-jwt-issuers`, standard oauth2-proxy
  flags) not configured in the L1 job today. This is not this ticket's
  problem to solve; flagging it here so the cutover ticket does not
  rediscover it from scratch.
- **Failure mode 5 — Bifrost rejects Switchyard's calls.**
  `client.enforce_auth_on_inference = true` (`bifrost.hcl:101`) means a
  missing/wrong virtual key 401s every request. The
  `null_resource.bifrost_ready` gate and the existing Hermes/Memex
  virtual-key pattern (Context) mitigate this at apply time; the live eval
  above is the first real check that the specific `provider_configs` on
  `bifrost_virtual_key.switchyard` actually resolve to a model Bifrost's
  current catalog serves.
- **Untestable this session:** everything requiring live Vault/Nomad/
  Consul CREDENTIALS (not network reachability — Premise P9, corrected:
  this session reached Consul, Bifrost, and 3 of 5 nodes via SSH, but has
  no Vault token or Nomad ACL token to apply anything). The implementer
  inherits the entire "Live evals" bucket in §8, plus re-confirming
  `radxa`'s live headroom immediately before committing to it (Premise
  P10) and resolving the `firebat`/`orange_pi_4a` host-key anomaly if
  either node is ever considered instead (Premise P9a).

## 10. Subtickets (ordered)
1. ~~Settle Open Questions A and B with the operator~~ — **done by this
   ticket revision (2026-08-22).** Both forks are resolved with citations
   in §11; no operator input is required before implementation starts.
   Node placement remains a live-cluster check (not a blocking decision)
   to run at the start of step 2.
2. `deployments/applications`: MinIO bucket/user/credential wiring
   (`storage.tf`, `secrets.tf` Code surface items 2-3). No dependency on
   the built binary existing yet. `terraform validate`.
3. Off-cluster build + one-time manual publish to the bucket from step 2
   (§8). Needs the run node's live architecture AND LSE-atomics support
   confirmed first (`ssh <node> uname -m` AND `ssh <node> "grep -m1
   Features /proc/cpuinfo | grep -o atomics"` / `nomad node status`;
   Premise P18 — architecture match alone is not enough) and step 2's
   bucket/admin credential to exist.
4. `deployments/applications`: `switchyard.hcl` + `nomad_job.switchyard` +
   `bifrost_virtual_key.switchyard` + `vault_kv_secret_v2.bifrost_switchyard_key`
   (Code surface items 1, 4-6). Depends on 2 (the MinIO reader credential
   the `secret {}` block reads) and 3 (the artifact must exist in the
   bucket, or the first alloc's fetch 404s). `terraform validate`.
5. `deployments/infrastructure`: `oauth2-proxy-switchyard.hcl` + Vault OIDC
   client/secrets + `nomad_job.oauth2_proxy_switchyard` (Code surface items
   7-11). Depends on 4 (needs Switchyard's own node/port settled so
   `OAUTH2_PROXY_UPSTREAMS` and the constraint are correct). `terraform
   validate`.
6. `deployments/infrastructure`: HAProxy route (Code surface item 12).
   Depends on 5 (needs the new oauth2-proxy instance's port). `terraform
   validate`.
7. `deployments/infrastructure`: Grafana dashboard + `grafana.hcl` /
   `deployments/infrastructure/services.tf:368-390` wiring (Code surface items 13-15). Independent of
   steps 3-6; only needs step 4's `"prometheus"` service tag live.
   `terraform validate`.
8. `just pre_commit` clean on both roots; live `terraform plan`/`apply` +
   the "Live evals" list in §8, run by whoever has real cluster access.
9. Adversarial review (`.claude/rules/adversarial-reviews.md`).

## 11. Open questions

**Open Question A — how does `switchyard-server` get built and run, and on
which node? RESOLVED (operator-selected 2026-08-22): build off-cluster,
publish, fetch (the ticket's original A2).**

Concrete design (Requirement 7, Code surface items 1-3, §8):
1. **Build:** the repo's own `Dockerfile`'s `builder` stage, run standalone
   off-cluster, targeting the run node's live-confirmed architecture. Exact
   command in §8. Settled as a documented manual step, not a script — this
   repo has no infra CI (unchanged premise) and its own Non-goals already
   rule out speculative build tooling; a version bump is rare enough that
   re-deriving the command from this ticket's own text is an acceptable
   cost (Risk assessment, Failure mode 2). Not escalating this as a
   separate operator decision — the smaller-surface case is strong enough
   here that a new fork would just relitigate a call the repo's own
   conventions already make for it.
2. **Publish:** one new private MinIO bucket, `switchyard-artifacts`
   (`deployments/applications/storage.tf`'s `locals.buckets` map — no new
   Terraform resource TYPE, just one new map entry, per the existing
   memex/loki/datalake/mlflow-artifacts pattern), uploaded to once by hand
   using the existing MinIO admin credential (`default/minio/localstack`)
   — no new writer identity needed for a one-time step.
3. **Fetch:** Nomad's `artifact` stanza (`s3::` / go-getter, MinIO-
   compatible), credentialed via a first-in-repo `secret { provider =
   "vault" }` block reading a NEW, read-only `switchyard` MinIO identity's
   key — not a public bucket (does not actually work with go-getter's
   Minio path; Context) and not a `data "vault_kv_secret_v2"` source (would
   persist the credential in Terraform state; this repo's own stated
   preference is `ephemeral`, and the native `secret {}` block sidesteps
   the whole tradeoff). Full evidence chain in Context and Premises
   P12-P15.

For the record, the options this ticket's first draft weighed:
- **A1 — Ansible installs Rust + `cargo install` on the target node once;
  run via `raw_exec`.** *Not chosen.* Breaks the 100%-podman convention in
  the same way A2 does, AND ties compile-time resource cost to the
  smallest boards in the cluster, AND adds a new Ansible role — strictly
  more new surface than A2 for the same architectural break.
- **A3 — `podman build` the repo's own `Dockerfile` directly on the target
  node.** *Not chosen.* Same on-node compile-resource risk as A1, with no
  offsetting benefit once A2 already proves out `raw_exec` is unavoidable
  regardless (no image is ever produced or pulled either way).

**Node placement — recommendation reversed by live data this revision
(Premise P10). `radxa`, not `jetson-orin-nano`.** The prior revision's
Nomad-reservation-based case for `jetson-orin-nano` (1 job, 512 MB
reserved) does not survive contact with live reality: a direct `ssh`
probe (P10) shows `jetson_nano` has only 389 MiB actually available right
now — memory-critical, not lightest. `radxa` (192.168.2.50), despite
running the most jobs (7, Context — including the now-`done` L1
oauth2-proxy), has by far the most live headroom of any probed node (5.4
GiB available, 8 CPUs) and is confirmed `aarch64`. **Recommend
`radxa-dragon-q6a`** for both `switchyard` and `oauth2-proxy-switchyard` —
this also puts Switchyard on the SAME node Bifrost already runs on
(lowest-latency passthrough hop), and its architecture is now confirmed
live, not inferred (Risk assessment, Failure mode 1). `firebat` and
`orange_pi_4a` are not recommended: both remain genuinely unverified
(Premise P9a) pending their SSH host-key mismatch. Before `terraform
apply`: re-confirm `radxa`'s live headroom (state can drift) and check
`radxa` for port conflicts with its other 7 jobs on `4000`/`4181`
(unverified this session — none of this ticket's citations confirm the
other jobs' exact port allocations). **If `radxa` turns out unsuitable at
apply time, `raspberry_pi_4b` is NOT a safe fallback despite being
`aarch64` and having the second-most headroom** (Premise P18): its
Cortex-A72 lacks the LSE atomics Switchyard's default aarch64 build
targets (`target-cpu=neoverse-n1`), and a binary built per §8's default
command would very likely `SIGILL` there. The only other confirmed-safe
node is `jetson-orin-nano` (Cortex-A78AE, LSE-capable) — despite its live
memory pressure (Premise P10), which would need addressing first.
`firebat`/`orange_pi_4a` remain unverified on both architecture AND
CPU-feature grounds (Premise P9a). If neither `radxa` nor
`jetson-orin-nano` proves workable, that is an operator decision, not a
silent pick.

**Open Question B — what inbound-auth mechanism gates
`switchyard.lab.orangecluster.nl`? RESOLVED (operator-selected 2026-08-22,
mirroring L1): a second, Switchyard-scoped oauth2-proxy instance (B5,
below).**

- **B5 — a second oauth2-proxy Nomad job, `oauth2-proxy-switchyard`,
  mirroring the now-`done` L1 job.** *Selected.* L1 shipped and is `done`
  (Premise P2, corrected from the ticket's first draft); the mechanism
  itself is proven, and its two blocked follow-ons (R1, R4) failed on
  backend-specific integration gaps, not the gate. Concrete design,
  citations, and code surface: Context, Requirement 6, Code surface items
  7-11. Real, accepted cost: this ships a human-browser OIDC gate, not a
  Bearer-token gate for a machine client (Non-goals, Risk assessment
  Failure mode 4) — the same cost L1, R1, and R4 all carry, and the
  reason a future cutover ticket needs oauth2-proxy's
  `--skip-jwt-bearer-tokens` mode (Risk assessment, non-blocking note for
  that later ticket, not this one).

For the record, the options this ticket's first draft weighed:
- **B1 — new HAProxy static Bearer-token ACL.** *Not chosen (was the first
  draft's recommendation).* Composes more cleanly with a future
  Bearer-token API client in the abstract, but the operator chose to
  reuse the repo's one PROVEN "gate a service with no native auth" pattern
  (oauth2-proxy, now confirmed `done`) over a net-new HAProxy mechanism
  with zero track record of its own in this repo.
- **B2 — reuse HAProxy Basic Auth exactly as Phoenix does it.** *Not
  chosen.* Same header-collision problem with a future Bearer-token
  consumer as B1 flagged against it, without B5's proven-pattern
  advantage.
- **B3 — oauth2-proxy, generically.** *Superseded by B5*, which is the
  same mechanism, now concretely designed and no longer blocked by "0-for-3
  in this repo" — that framing was itself based on the stale ledger
  snapshot corrected in Premise P2.
- **B4 — depend on `N4-netsec-edge-only-service-access` landing first,
  defer inbound auth.** *Not chosen.* N4 narrows LAN-wide exposure, it
  does not add forward-auth, so it would not satisfy this ticket's
  explicit requirement to ship a working inbound gate.

**No new blocking fork surfaced during this revision.** Both open
questions and the stale premise are resolved with citations; the only
items still deferred to implementation time are live-cluster checks
(node architecture/headroom) that the ticket already, correctly, does not
try to settle from this network-isolated authoring session.

## Premises / assumptions

- **P1: the Bifrost virtual-key pattern (per-consumer key, stored in
  Vault, read by `vault {}` + `template`) is live and shipped, not just
  planned.** Anchor: `deployments/applications/services.tf:274-375`,
  `deployments/applications/secrets.tf:85-104`. probe: `loopctl ledger |
  grep B1-bifrost`, captured 2026-08-22: `done`.
- **P2 (CORRECTED this revision): oauth2-proxy-style forward-auth IS a
  proven, live pattern in this repo — L1 is `done`.** The ticket's first
  draft claimed no such ticket had ever reached `done`, citing a
  2026-08-22 `loopctl ledger` snapshot showing L1/R1/R4 all `blocked`;
  that snapshot was stale by the time of writing. probe:
  `loopctl ledger | grep -E 'L1|R1-|R4-'`, re-captured 2026-08-22:
  `L1-landing-oauth2-proxy: done`; `R1-rollout-mlflow-oauth2-proxy: blocked
  [... mlflow#10922 closed not_planned ... MLflow now ships an SSO
  plugin]`; `R4-rollout-phoenix-oauth2-proxy: blocked [... Phoenix
  hard-requires an email claim, Vault emits none ...]`. Anchor for the
  shipped mechanism: commit `e48742e`
  ("L1-landing-oauth2-proxy: deploy oauth2-proxy as the landing-page OIDC
  gate"), `deployments/infrastructure/services/oauth2-proxy.hcl` (whole
  file, new), `deployments/infrastructure/oidc.tf:164-187`. R1's and R4's
  blockers are specific to their own backends (a closed-not-planned
  MLflow issue plus MLflow's own new SSO plugin; Phoenix's hard email-
  claim requirement against Vault's claim-less ID token), not to
  oauth2-proxy itself.
- **P3: HAProxy's own HTTP Basic Auth IS live today, gating `phoenix`.**
  Anchor: `deployments/infrastructure/services/haproxy.hcl:142-144`
  (re-verified line numbers post-L1), credential source
  `deployments/infrastructure/secrets.tf:32-43`.
- **P4: `switchyard-server` ships with zero inbound authentication.**
  Anchor (external, `main` branch, fetched 2026-08-22):
  https://github.com/NVIDIA-NeMo/Switchyard/blob/main/crates/switchyard-server/src/lib.rs#L599-L601
  (the only two router-level
  middleware layers are `DefaultBodyLimit` and a timestamp stamp);
  `docs/cli_reference.md` (no `--auth`/`--api-key` flag).
- **P5: no prebuilt `switchyard-server` binary or image is published
  upstream.** probe: `curl -sS https://api.github.com/repos/NVIDIA-NeMo/Switchyard/releases`,
  captured 2026-08-22: `v0.2.0` → `"assets": []`. probe: `curl -sS
  https://raw.githubusercontent.com/NVIDIA-NeMo/Switchyard/main/.github/workflows/publish.yml`,
  captured 2026-08-22: publishes to PyPI + crates.io only, no
  docker build/push job.
- **P6: every existing Nomad job in this repo pulls a prebuilt image via
  `podman`; none builds from source or uses `raw_exec`.** probe: `grep -rn
  'driver = "podman"' deployments/*/services/*.hcl deployments/*/services/**/*.hcl`,
  re-verified 2026-08-22: 24 hits, 0 counterexamples; `grep -rln raw_exec
  deployments/` (excluding `.terraform`): no hits.
- **P7: `raw_exec` is already enabled on every Nomad client and server,
  unused by any current job.** Anchor:
  `bootstrap/roles/nomad_client/templates/nomad.hcl.j2:65-69`,
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:92-96`.
- **P8: the Rust toolchain and Switchyard's own Dockerfile base images
  officially support `aarch64`/arm64.** probe: `curl -sS
  https://raw.githubusercontent.com/NVIDIA-NeMo/Switchyard/main/Dockerfile`,
  re-fetched 2026-08-22: `FROM rust:${RUST_VERSION}-bookworm AS builder`
  (with `RUST_VERSION=1.96.1`) then `FROM debian:bookworm-slim`, no
  `--platform`/cross-compile flag. source:
  https://hub.docker.com/_/rust and https://hub.docker.com/_/debian —
  both are official multi-arch images published for `linux/arm64`;
  `aarch64-unknown-linux-gnu` is a Rust Tier-1 target. This is
  well-established, third-party-documented tool behavior, not something
  this session independently benchmarked on the target SBC hardware — see
  P10 for what remains genuinely uncertain.
- **P9 (CORRECTED this revision): the cluster IS reachable from an
  implementation/review session — the earlier "no network path" claim was
  an artifact of one sandboxed authoring session, not a fact about the
  cluster's real reachability.** The ticket's first two drafts each ran
  `timeout 3 bash -c 'cat < /dev/tcp/192.168.2.30/22'`, got a timeout from
  their own sandbox, and concluded no route existed. This revision's
  plan-validator review pass, in a different sandbox, reached Consul's
  catalog, Bifrost's `/health`, and got a genuine Nomad ACL rejection (a
  real response, not a timeout) — and re-probing independently confirms
  it: `timeout 4 curl -fsS http://192.168.2.30:8500/v1/catalog/nodes`
  returns the real 5-node catalog (`firebat`, `jetson_nano`,
  `orange_pi_4a`, `radxa`, `raspberry_pi_4b`, Consul version `2.0.2`);
  `timeout 4 curl -fsS http://192.168.2.50:8080/health` returns Bifrost's
  real `{"components":{"db_pings":"ok"},"status":"ok"}`; SSH (using the
  repo's own `.ssh/id_rsa`, per `bootstrap/inventory/cluster.ini`'s
  per-node `ansible_user`) succeeded to `jetson_nano`
  (`localstack@192.168.2.46`), `raspberry_pi_4b`
  (`raspberry@192.168.2.47`), and `radxa` (`radxa@192.168.2.50`) — live
  `uname -m`/`nproc`/`free -h` captured for all three (Premise P10).
  Network reachability is a property of WHICH sandbox an agent runs in,
  not a fixed fact about this repo or cluster — do not re-assert "no
  network path" in a future revision without re-probing first.
- **P9a (NEW): SSH to `firebat` (192.168.2.30) and `orange_pi_4a`
  (192.168.2.29) refused with `REMOTE HOST IDENTIFICATION HAS CHANGED` (a
  host-key mismatch against `~/.ssh/known_hosts`), not a timeout or
  connection refusal.** This session did NOT bypass
  `StrictHostKeyChecking` to work around it — a changed host key is
  either a benign reimage of those two nodes or a genuine MITM/security
  concern, and distinguishing the two is the operator's call, flagged
  outside this ticket, not an authoring session's to silently resolve.
  This is why `firebat`'s and `orange_pi_4a`'s architecture remain
  unverified (Premise P10) even though the network itself is reachable —
  a host-identity anomaly on those two specific nodes, not a routing gap.
- **P10 (PARTIALLY RESOLVED this revision — live data for 3 of 5 nodes;
  `firebat`/`orange_pi_4a` still UNCERTAIN per P9a).** Live probes
  (`ssh <user>@<host> 'uname -m; nproc; free -h'`, captured 2026-08-22,
  users from `bootstrap/inventory/cluster.ini`):
  - `jetson_nano` (`localstack@192.168.2.46`): `aarch64`, 6 CPUs, **389
    MiB available of 7.4 GiB** (used 6.7Gi, buff/cache 630Mi) —
    memory-critical RIGHT NOW, contradicting this ticket's own
    Nomad-reservation-based case (Context: "lightest node ... by reserved
    memory") against live reality. Nomad's `memory = 512` reservation for
    `memex` does not reflect what's actually free on the box.
  - `raspberry_pi_4b` (`raspberry@192.168.2.47`): `aarch64`, 4 CPUs, 2.6
    GiB available.
  - `radxa` (`radxa@192.168.2.50`): `aarch64`, 8 CPUs, **5.4 GiB
    available** — the most headroom of any probed node, despite running
    the most jobs (7, Context).
  - `firebat` and `orange_pi_4a`: still UNCERTAIN — SSH blocked by a
    host-key mismatch, not a routing failure (Premise P9a). Indirect
    evidence (100% `linux_arm64` Terraform provider downloads; every
    OTHER node in the cluster now confirmed `aarch64`) still leans toward
    both being `aarch64` too, but remains circumstantial for these two
    specifically.
  This live data reopens Open Question A's node-placement recommendation
  — see its updated text: `jetson-orin-nano`'s theoretical "lightest
  node" case does not survive contact with its actual free memory;
  `radxa` now has the strongest live-headroom case despite the highest
  job count.
- **P11: HAProxy's live oauth2-proxy pattern is a reverse-proxy gate
  (HAProxy proxies straight through oauth2-proxy to nothing else, since
  oauth2-proxy fronts the real origin), not a forward-auth sidecar
  (HAProxy asking a separate auth service "allow?" then proxying
  elsewhere on approval).** Anchor: `deployments/infrastructure/services/haproxy.hcl:155-156`
  (`backend dash` → `server dash1 192.168.2.50:4180 check`, oauth2-proxy's
  own port, no separate "dash" application exists behind it); `deployments/infrastructure/services/oauth2-proxy.hcl:54`
  (`OAUTH2_PROXY_UPSTREAMS="static://200"` — an authenticated request gets
  a static 200 from oauth2-proxy itself). probe: `grep -n
  'auth_request\|auth-request' deployments/infrastructure/services/haproxy.hcl`,
  captured 2026-08-22: no output, exit code 1 (zero hits) — confirmed no
  `auth-request`-style directive exists anywhere in the file.
- **P12: a public-read MinIO bucket alone does not let Nomad's `artifact`
  stanza fetch an object without credentials — go-getter's S3 getter has
  no anonymous/unsigned-request mode for MinIO targets, even though
  MinIO's own ACL system genuinely does support anonymous-read buckets.**
  source: raw.githubusercontent.com/hashicorp/go-getter/main/README.md,
  fetched 2026-08-22, "Using S3 with Minio": "`aws_access_key_id`
  (required)... `aws_access_key_secret` (required)" (contrast with plain
  AWS S3's optional IAM-instance-profile fallback, same doc). Code-level
  confirmation: `get_s3.go`'s `getAWSConfig` (raw.githubusercontent.com/
  hashicorp/go-getter/main/get_s3.go, fetched 2026-08-22) only sets a
  credentials provider when static creds or an `AWS_METADATA_URL`
  override are present; otherwise it falls through to the AWS SDK's
  default chain, which resolves nothing on a non-EC2 host with no AWS env
  vars and fails the signed request regardless of the bucket's own policy.
  For contrast, MinIO's own Terraform provider (`aminueza/
  terraform-provider-minio`) DOES implement a real anonymous-read bucket
  policy for `acl = "public-read"`/`"public"` via `SetBucketPolicy`
  (`resource_minio_s3_bucket.go`, fetched 2026-08-22, `defaultPolicies`
  map + the `SetBucketPolicy` call) — the MinIO side of "public" is real,
  go-getter simply never tries the unauthenticated request that would
  benefit from it.
- **P13: Nomad's native `secret {}` job-spec block (Nomad 1.11.0+, GH-26681)
  lets `artifact.options` reference a Vault-issued value via
  `${secret.<name>.<key>}`, using the SAME task-level `vault {}` token and
  the SAME underlying `{{ with secret "<path>" }}` Consul-Template
  mechanism the `template` stanza already uses everywhere in this repo —
  so it carries zero new Vault-policy surface.** source:
  raw.githubusercontent.com/hashicorp/nomad/main/CHANGELOG.md, fetched
  2026-08-22, `1.11.0` entry: "secrets: Adds secret block for fetching and
  interpolating secrets in job spec [GH-26681]". This cluster pins Nomad
  `2.0.4-1` (`bootstrap/inventory/group_vars/all.yml:12`), newer than
  1.11.0. Mechanism confirmation:
  `client/allocrunner/taskrunner/secrets/vault_provider.go`
  (`hashicorp/nomad` `main` branch, fetched 2026-08-22) — `BuildTemplate()`
  emits `{{ with secret "<v.secret.Path>" }} ... {{ end }}`, `.Data.data`
  when `config.engine = "kv_v2"`, identical to this repo's own `template`-
  block convention (documented in-repo at
  `deployments/infrastructure/services/haproxy.hcl:46-47`'s comment about
  `.Data.data.x`). Interpolation-into-`artifact.options` confirmed by the
  artifact doc's own worked example:
  `aws_access_key_id = "${secret.aws.key_id}"`
  (developer.hashicorp.com/nomad/docs/job-specification/artifact, fetched
  2026-08-22).
- **P14: go-getter's S3 getter writes fetched objects at file mode 0666
  (no execute bit); Nomad's `artifact` block has no `perms` parameter to
  override this.** source: go-getter's `get_s3.go` line 211
  (raw.githubusercontent.com/hashicorp/go-getter/main/get_s3.go, fetched
  2026-08-22): `return copyReader(dst, body, 0666, g.client.umask(), 0)`.
  Confirmed against the artifact block's documented parameter list
  (`destination`, `mode`, `options`, `headers`, `source`, `chown` — no
  `perms`), same doc as P13.
- **P15: the repo's generic, `for_each`-driven
  `vault_kv_secret_v2.minio_credentials` resource
  (`deployments/applications/secrets.tf:117-124`, writing to
  `default/minio/<name>`) is NOT what a same-named Nomad job's
  `nomad-workloads` grant covers; every live MinIO-backed Nomad job uses
  its own explicitly-named resource under its own job-id KV prefix
  instead.** Anchor: `vault_kv_secret_v2.memex_minio_credentials` at
  `default/memex/minio` (`deployments/applications/secrets.tf:31-38`,
  consumed by `deployments/applications/services/memex.hcl:122,124` via
  `deployments/applications/services.tf:254`'s `memex_minio_secret` var);
  `vault_kv_secret_v2.loki_minio_credentials` at `default/loki/minio`
  (`deployments/applications/secrets.tf:42-48`, consumed via
  `deployments/applications/services.tf:167`'s `loki_minio_secret`
  var). Cross-checked against the WI-derived grant template itself:
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-9`
  grants exactly `secret/data/<namespace>/<job_id>/*` — `default/minio/*`
  is outside that path for a job named anything other than `minio`.
- **P16 (RESTORED this revision — an earlier attempt to withdraw this
  premise was itself wrong): this cluster's downloaded Terraform provider
  cache includes both `linux_arm64` and `darwin_arm64` builds of the
  MinIO provider**, weak circumstantial evidence that at least one
  operator workstation is Apple-Silicon — reinforcing why §8's build step
  uses a containerized, `--platform`-pinned build rather than assuming a
  native-architecture match on the operator's own machine. probe: `ls -la
  deployments/applications/.terraform/providers/registry.terraform.io/aminueza/minio/3.8.3/`
  and the same path under `deployments/applications/modules/bucket/.terraform/`,
  captured 2026-08-22: both list `darwin_arm64/` and `linux_arm64/`. A
  prior revision of this ticket wrongly marked this premise WITHDRAWN
  based on `find deployments -maxdepth 3 -iname ".terraform" -type d`
  returning no hits — that specific `find` invocation is unreliable in
  this environment for dot-directories (`command find <exact-path>` with
  no name filter, and plain `ls`/`stat` on the known path, all confirm
  the directory is real and dated 2026-07-31); this premise gates nothing
  load-bearing either way, but the correct lesson is to cross-check a
  negative `find` result against `ls`/`stat` before treating absence as
  proven.
- **P17: the "zero prior use of Nomad's `artifact`/`secret` blocks"
  Context claim, verified with a pattern that excludes Consul-Template
  false positives.** A naive `grep -rln 'artifact {\|secret "'
  deployments/` (excluding `.terraform/`) returns 15 hits (files), all
  containing `{{ with secret "<path>" }}` Consul-Template interpolations
  already used in every job's `template` block (e.g.
  `deployments/applications/services/hermes.hcl:183,188,194,197,200`) —
  that string contains `secret "` without being the Nomad `secret {}`
  block this ticket introduces. probe: `grep -rn '^\s*artifact\s*{\|^\s*
  secret\s*"[a-zA-Z_]*"\s*{' deployments/` (excluding `.terraform/`),
  captured 2026-08-22: zero hits — the underlying claim (no prior use of
  either block) holds under the correct pattern.
- **P18 (NEW, most dangerous premise in this ticket): `aarch64` alone is
  NOT sufficient CPU compatibility for this build — Switchyard's own
  build config targets a specific ARMv8.1+ microarchitecture feature
  (LSE atomics) that NOT ALL of this cluster's aarch64 boards have.**
  source: `.cargo/config.toml` at the repo root (`NVIDIA-NeMo/Switchyard`,
  `main` branch, fetched 2026-08-22):
  `[target.aarch64-unknown-linux-gnu]` sets `rustflags = ["-C",
  "target-cpu=neoverse-n1", ...]` — Neoverse N1/Graviton2-class, which
  requires LSE atomic instructions (ARMv8.1-A). Live probe (`grep -m1
  'CPU part' /proc/cpuinfo; grep -m1 Features /proc/cpuinfo | grep -o
  atomics`, captured 2026-08-22): `radxa` (CPU part `0xd05`, Cortex-A55)
  and `jetson_nano` (CPU part `0xd42`, Cortex-A78AE) both report
  `atomics` in `/proc/cpuinfo` Features — LSE-capable, safe for the
  default build. `raspberry_pi_4b` (CPU part `0xd08`, Cortex-A72,
  ARMv8.0-A) does NOT report `atomics` — a binary built per §8's default
  command would very likely `SIGILL` on it. **This directly breaks the
  prior revision's stated fallback** ("if `radxa` turns out unsuitable...
  `raspberry_pi_4b` is the live-verified fallback") — that fallback is
  WRONG as stated; see Open Question A's corrected text and Requirement
  7/§8's updated build guidance.
