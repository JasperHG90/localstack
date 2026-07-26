---
epic = "rollout"
depends_on = ["L1-landing-oauth2-proxy", "A1-audit-plan-premise-sweep"]
priority = 5
summary = "Front the MLflow tracking server with oauth2-proxy: humans via Vault OIDC auth-code flow, machines via Nomad Workload Identity bearer JWTs, replacing MLflow's shared HAProxy basic-auth gate. MLflow has no native SSO."
tags = ["mlflow", "oauth2-proxy", "oidc", "haproxy"]
---

# R1: Front MLflow with oauth2-proxy (Vault OIDC for humans, Nomad WI bearer for machines)

## 1. Title

Put the MLflow tracking server behind an oauth2-proxy that authenticates
humans via Vault OIDC (auth-code flow) and validates Nomad Workload
Identity `Authorization: Bearer` JWTs for machines, replacing MLflow's
current HAProxy basic-auth gate, and route it through HAProxy.

## 2. Size / Effort

**M.** One new proxy job (or sidecar) plus its Vault-templated config,
one Terraform wiring change to deploy it, one HAProxy backend rewrite,
one secrets resource for the OIDC client, and one caveat doc. What
drives the size is not line count but the two forks the operator must
settle first (where the proxy runs / whether it is dedicated or shared)
and the cross-layer split: the MLflow job lives in the **applications**
Terraform layer while HAProxy lives in the **infrastructure** layer, so
the change touches two Terraform states. It is not L because no new
Ansible role or cluster bootstrap is required; oauth2-proxy runs as a
Nomad Podman task like every other service here.

## 3. Triggered by

Auth epic, stage R1 (per-service rollout). MLflow has no native OIDC —
the upstream SSO request is open issue mlflow/mlflow#10922, confirmed by
the S3 spike finding — so authentication must be added at a reverse
proxy in front of it. This ticket is the first concrete per-service
rollout of the L1 forward-auth pattern against a real service.

## 4. Context

Today MLflow is authenticated only by shared HTTP basic auth at the
HAProxy edge, and MLflow itself is wide open on the LAN.

- The MLflow Nomad job is `deployments/applications/services/mlflow.hcl`
  (NOT under `infrastructure/services/` as the epic brief states — it is
  in the **applications** layer). It runs `mlflow server` on
  `radxa-dragon-q6a`, static port 5050, `network_mode = host`
  (`mlflow.hcl:11-15,40,42`), pinned by hostname constraint
  (`mlflow.hcl:6-9`). It already has a `vault {}` block
  (`mlflow.hcl:45`) and a Vault-templated `secrets/file.env` with
  `env = true` (`mlflow.hcl:47-60`), the injection pattern this ticket
  reuses for the proxy's client secret and cookie secret.
- MLflow is deployed by `nomad_job.mlflow` at
  `deployments/applications/services.tf:187-200`, which passes
  `mlflow_host = "192.168.2.50"` and `mlflow_version = "2.20.0"` via
  `templatefile`.
- The current authn is HAProxy basic auth, NOT OIDC. In
  `deployments/infrastructure/services/haproxy.hcl`: the `openfang_users`
  userlist is defined at `haproxy.hcl:45-46`, the MLflow ACL at
  `haproxy.hcl:61`, the route at `haproxy.hcl:74`, and the backend at
  `haproxy.hcl:115-117` gates every request with
  `http-request auth unless { http_auth(openfang_users) }`
  (`haproxy.hcl:116`) before proxying to `192.168.2.50:5050`
  (`haproxy.hcl:117`). This single shared password is what per-user
  Vault login replaces.
- **HAProxy has no TLS.** The only bind is `bind *:80`
  (`haproxy.hcl:49`); there is no `bind :443`, no cert, no `ssl`
  keyword anywhere in the file. The epic's "route behind TLS" cannot be
  satisfied by R1 without introducing TLS termination that does not
  exist today. See Open Question Q4.
- **oauth2-proxy does not exist in the repo yet.** A tree-wide search
  for `oauth2`, `oauth2-proxy`, `forward-auth`, and `oidc` across
  `*.hcl`/`*.tf` returns no service job and no Terraform — the only hit
  is the sibling plan `.loop/plans/S1-spike-boundary-evaluation.md`. R1
  therefore depends on L1 to establish the reusable pattern (see
  Dependencies and Q1).
- Machine identity already exists: Nomad issues Workload Identity JWTs.
  The default identity is Vault-audience only —
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42-45`
  (`default_identity { aud = ["vault.io"] ttl = "1h" }`). For a job to
  push to MLflow keylessly it needs a **second** identity block whose
  `aud` matches what the proxy validates, and the proxy must trust
  Nomad's JWKS/OIDC-discovery issuer. Neither exists yet.
- The secret-provisioning pattern to copy is the openfang basic-auth
  resource: `random_password` + `vault_kv_secret_v2` at
  `deployments/infrastructure/secrets.tf:32-44`. MLflow's own service
  credentials follow the same shape at
  `deployments/applications/secrets.tf:53-67`.
- The reverse-proxy how-to doc that will need a new entry is
  `docs/haproxy_reverse_proxy.md` (see its "Adding a New Service"
  section).

What is wrong/missing: MLflow authn is a single shared password at the
edge with no per-user identity and no machine-token path, so pipelines
cannot push keylessly and there is no audit of who logged in.

## 5. Non-goals / out of scope

- **No fine-grained MLflow authorization.** MLflow's built-in auth
  plugin is thin; the proxy gates *access* (authn) but does not give
  per-experiment or per-model authz. This limit MUST be documented (see
  Requirements R6), not solved.
- **No cluster-wide TLS rollout.** Adding `bind :443` + certificates to
  HAProxy is a separate concern (the edge is plain HTTP:80 today). R1
  documents the gap; it does not build TLS unless the operator scopes it
  in via Q4.
- **No rollout to other services.** Grafana, MinIO console, Phoenix,
  Bifrost, etc. keep their current gates. R1 is MLflow only.
- **Not building the L1 pattern from scratch.** If L1 has not landed a
  reusable oauth2-proxy job/module, R1 is blocked on it (Q1), not a
  place to re-invent it.
- **Not configuring Vault as an OIDC provider.** That is F2. R1 consumes
  a Vault OIDC client; it does not stand up the provider.
- **Not removing MLflow's LAN firewall rule.** The ufw rule opening 5050
  to the LAN (`deployments/applications/services.tf:58-65`) is a
  separate hardening step; see Q5.

## 6. Requirements & restrictions

The change MUST:

1. **Front MLflow with oauth2-proxy** reusing the L1 forward-auth
   pattern, so all MLflow traffic terminates authn at the proxy before
   reaching `mlflow server` on 5050.
2. **Humans → Vault OIDC auth-code flow.** An unauthenticated browser
   hitting the MLflow UI is redirected to Vault to log in and returns
   authenticated. The OIDC client credentials are provisioned as a
   Vault secret (mirror `secrets.tf:32-44`) and injected via the
   existing `template { env = true }` mechanism (`mlflow.hcl:47-60`),
   never hardcoded (CLAUDE.md "Secrets: All in Vault KV2").
3. **Machines → Bearer JWT validation.** The proxy accepts a valid
   Nomad Workload Identity `Authorization: Bearer` JWT from a trusted
   issuer and passes the request through without an interactive login,
   so a pipeline job can call the MLflow REST API keylessly. This
   requires (a) a non-default Nomad `identity` block on the calling job
   with an `aud` the proxy accepts (contrast the Vault-only default at
   `nomad.hcl.j2:42-45`) and (b) the proxy trusting Nomad's JWKS. Both
   are part of this ticket's surface; see Q3.
4. **Block the unauthenticated path.** With the proxy in place, remove
   the now-redundant HAProxy basic-auth gate for MLflow
   (`haproxy.hcl:116`) so there is no double-prompt, and point the
   HAProxy `mlflow` backend at the proxy's listen port instead of 5050
   directly (`haproxy.hcl:117`). A request with neither a session cookie
   nor a valid Bearer token gets 401/redirect, not the MLflow UI.
5. **Route through HAProxy.** Keep the `mlflow.localstack` host-header
   route (`haproxy.hcl:61,74`); only the backend target and auth line
   change. Follow the doc's "Adding a New Service" convention in
   `docs/haproxy_reverse_proxy.md`.
6. **Document the authz caveat** in a doc: authn is at the edge, MLflow's
   own authz is thin, so anyone who authenticates reaches the whole
   MLflow API. This is a known limitation of the proxy approach.

Restrictions the repo enforces (each cited):

- **Simplicity / surgical changes** (CLAUDE.md sections 2-3): prefer the
  smallest working shape (one proxy task, reuse the existing Vault
  template block); do not refactor adjacent jobs or the HAProxy config
  beyond the MLflow backend and its auth line. Every changed line traces
  to this request.
- **Surface forks, do not pick silently** (CLAUDE.md section 1): the
  dedicated-vs-shared and where-it-runs decisions go to the operator
  (Open Questions), not a silent choice.
- **Secrets only in Vault KV2** (CLAUDE.md "Key Conventions"): the OIDC
  client secret and oauth2-proxy cookie secret are `vault_kv_secret_v2`
  resources injected via template, never inline in the HCL.
- **HCL formatting** (`.pre-commit-config.yaml` `nomad-fmt` hook; root
  `justfile` `format:` = `nomad fmt -recursive`): any new/edited `.hcl`
  must be `nomad fmt`-clean or `just pre_commit` fails.
- **Doc slop scan** (`.claude/rules/slop-scan-for-docs.md`): the caveat
  doc is markdown and must pass all three layers — no hallucinated
  paths/identifiers, thesis-first, American spelling, prose wrapped at
  80 chars, em-dash budget. Every backticked path must resolve.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`): hand
  the finished change to a review sub-agent before declaring done.

## 7. Code surface

Exact anchors and the change each carries. Because oauth2-proxy is new,
some entries are CREATE; the operator forks (Q1-Q2) decide which layer
owns them.

- **CREATE** an oauth2-proxy Nomad task/job — either a new task inside
  `deployments/applications/services/mlflow.hcl` (sidecar in the same
  group, sharing `network_mode = host` on 192.168.2.50) or a standalone
  `*.hcl` job. Carries: the OIDC provider config (Vault issuer, client
  id/secret from Vault template), the upstream (`http://127.0.0.1:5050`),
  skip-auth for `/health` (`mlflow.hcl:29`), and Bearer-JWT acceptance
  for the Nomad WI issuer. Decided by Q1/Q2.
- `deployments/applications/services/mlflow.hcl:47-60` — extend the
  existing `template { env = true }` block (or add a second) to inject
  the proxy's OIDC client secret and cookie secret if the proxy is a
  sidecar here.
- `deployments/applications/services.tf:187-200` — the `nomad_job.mlflow`
  `templatefile` vars; add the proxy client-secret path and any new
  template inputs, mirroring how `mlflow_postgres_secret` is passed
  (`services.tf:191`). If the proxy is a standalone job, add a sibling
  `nomad_job` resource here instead.
- `deployments/applications/secrets.tf:53-67` (or infra
  `secrets.tf:32-44`) — add a `random_password` (cookie secret) and a
  `vault_kv_secret_v2` holding the OIDC client id/secret, following the
  openfang/mlflow resource shape. Layer depends on Q2.
- `deployments/infrastructure/services/haproxy.hcl:116` — remove the
  `http-request auth unless { http_auth(openfang_users) }` line for the
  `mlflow` backend (redundant once the proxy authenticates).
- `deployments/infrastructure/services/haproxy.hcl:117` — repoint the
  backend `server` from `192.168.2.50:5050` to the oauth2-proxy listen
  address/port.
- `docs/haproxy_reverse_proxy.md` — add/adjust the MLflow entry to note
  it now sits behind oauth2-proxy, per the "Adding a New Service"
  convention.
- **CREATE** the caveat doc, e.g. `docs/mlflow_oauth2_proxy.md` (path is
  Q6) — records the human/machine auth flows and the thin-authz
  limitation from Requirement R6.

## 8. Tests & validation gates

- **Repo gate:** `just pre_commit` (root `justfile` `pre_commit:` recipe
  → `pre-commit run --all-files`). This gate is now Terraform-aware.
  Configured hooks (`.pre-commit-config.yaml`): check-json, check-ast,
  check-merge-conflict, check-yaml (`--unsafe`), debug-statements,
  detect-private-key, end-of-file-fixer, and three local hooks —
  `nomad-fmt` (`entry: nomad fmt -recursive`, `files: '\.hcl$'`),
  `terraform-fmt` (`entry: terraform fmt -check -recursive`,
  `types: [terraform]`), and `terraform-validate` (`entry:
  scripts/tf_validate.sh`, `types: [terraform]`). Because the terraform
  hooks key on `types: [terraform]`, every edited `.tf` under
  `deployments/` is now `terraform fmt`-checked and offline-`validate`d:
  `scripts/tf_validate.sh` runs `terraform validate` against each root
  (`deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`) with `init -backend=false`,
  so it never touches the Consul backend. This retires the former
  "Terraform is not validated by the gate" caveat: any new/changed `.tf`
  in this ticket (the `nomad_job`, `random_password`, and
  `vault_kv_secret_v2` resources) must pass `fmt -check` and `validate`,
  and every edited `.hcl` must be `nomad fmt`-clean, or `just pre_commit`
  fails. The new doc must end with a newline and must not trip
  detect-private-key. `.pre-commit-config.yaml:1` excludes
  `^\.(claude|loop)/`, so this ticket file is not linted, but files
  under `deployments/` and `docs/` ARE.
- **No Python test harness for this change.** This is Terraform/HCL
  infra with no Python; the `all-code-needs-tests` rule
  (`.claude/rules/python-testing.md`) targets code and there is no HCL
  unit harness here. The `terraform validate` gate above plus the live
  evals below are the verification. Do NOT invent a test framework.

- **Evals (live).** The cluster is reachable from this environment —
  `VAULT_ADDR`/`VAULT_TOKEN`, `NOMAD_ADDR`/`NOMAD_TOKEN`, and
  `CONSUL_HTTP_ADDR` are set — so the acceptance below is runnable, not
  hypothetical. Run each after `terraform apply` of the affected
  layer(s). These evals **depend on L1 (the oauth2-proxy pattern) and
  F2 (Vault as OIDC provider registering the MLflow client)**; if either
  is not landed, the human and machine flows cannot pass and R1 is
  blocked (Q1). Scheme is `http://` because the edge is plain HTTP:80
  today (`haproxy.hcl:49`, Q4); switch to `https://` only if Q4 puts TLS
  in scope. Each eval is a command plus its expected result.

  1. **Allocs healthy.** MLflow and its oauth2-proxy are running.
     - Command: `nomad job status mlflow` (and `nomad job status
       <proxy-job>` if the proxy is a standalone job per Q2).
     - Expected: the `mlflow` task and the oauth2-proxy task both report
       `running`/`healthy`; deployment `Status = successful`.

  2. **Human path — unauthenticated redirect to Vault.** A browserless
     request to the UI is bounced to Vault OIDC, not served MLflow.
     - Command: `curl -sI http://mlflow.localstack/`
     - Expected: `HTTP/1.1 302` (or 307) with a `Location:` header
       pointing at the Vault OIDC authorize endpoint on
       `http://192.168.2.30:8200` (`$VAULT_ADDR`), NOT `200` and NOT the
       MLflow HTML.

  3. **Machine path — Nomad WI Bearer JWT accepted.** A request carrying
     a valid Nomad Workload Identity JWT (correct `aud`, trusted issuer)
     reaches the MLflow REST API with no interactive login. Obtain the
     JWT from the WI-enabled alloc created by subticket 4 (the
     non-default `identity { ... file = true }` block), e.g. read its
     identity file:
     `TOKEN=$(nomad alloc exec <alloc-id> cat /secrets/mlflow_wi.jwt)`.
     - Command:
       `curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer
       $TOKEN" http://mlflow.localstack/api/2.0/mlflow/experiments/search`
       (endpoint is `experiments/search`; MLflow 2.20.0 removed the old
       `experiments/list`).
     - Expected: `200`, with a JSON experiments payload — proving the
       proxy validated the Bearer JWT and forwarded to MLflow without a
       login redirect.

  4. **Unauthenticated API blocked.** A request with neither a session
     cookie nor a valid Bearer token does not reach the MLflow API.
     - Command:
       `curl -s -o /dev/null -w '%{http_code}'
       http://mlflow.localstack/api/2.0/mlflow/experiments/search`
     - Expected: `401` (or a `302` login redirect), NOT `200`.

  5. **Old HAProxy basic auth is gone.** The removed
     `openfang_users`/`http_auth` gate (`haproxy.hcl:116`) no longer
     fronts MLflow, so there is no basic-auth prompt and no double-auth.
     - Command: `curl -sI http://mlflow.localstack/` and inspect
       headers; also confirm the running HAProxy config no longer has
       the auth line for the `mlflow` backend (`nomad alloc exec
       <haproxy-alloc> grep -A3 'backend mlflow' <cfg>`).
     - Expected: no `WWW-Authenticate: Basic` header on the MLflow route,
       and no `http-request auth ... http_auth(openfang_users)` in the
       live `mlflow` backend — only the oauth2-proxy redirect from
       eval 2.

  6. **Health check stays green.** `/health` is skip-auth so the Consul
     check (`mlflow.hcl:27-32`) does not flap.
     - Command: `curl -s -o /dev/null -w '%{http_code}'
       http://mlflow.localstack/health` and `consul catalog services |
       grep mlflow` / `nomad job status mlflow`.
     - Expected: `/health` returns `200` unauthenticated and the
       `mlflow` service check is passing.

  7. **Load-bearing risk — one proxy, both issuers (Q3).** This is the
     eval that proves the primary technical risk is resolved: a SINGLE
     oauth2-proxy instance must serve BOTH the Vault OIDC auth-code login
     (eval 2) AND Nomad WI Bearer-JWT validation (eval 3) across two
     different issuers. Run evals 2 and 3 against the same running proxy
     alloc and confirm both pass without reconfiguring between them.
     - Expected (success): eval 2 returns 302-to-Vault and eval 3
       returns 200, from the same instance — record this as the resolved
       Q3 path (e.g. `--skip-jwt-bearer-tokens` + Nomad JWKS as an added
       trusted issuer).
     - Expected (fallback): if one instance cannot trust both issuers,
       do NOT silently narrow R1 to humans-only. Record the fallback
       actually taken (a dedicated bearer-validation path, or Nomad WI
       tokens minted with the Vault-OIDC audience) in the caveat doc and
       Open Question Q3, and show that both evals 2 and 3 still pass
       under that fallback.

- **Adversarial review** (`.claude/rules/adversarial-reviews.md`):
  before reporting done, a review sub-agent checks the flows, the
  removed basic-auth line, the backend repoint, the resolved-or-recorded
  Q3 outcome, and that no secret is inlined.

**Eval marker.** These seven scenarios are encoded as the loop's
Definition of Done in `.loop/evals/R1-rollout-mlflow-oauth2-proxy.md`
(validated by `loopctl eval R1-rollout-mlflow-oauth2-proxy`).

## 9. Risk assessment

- **Blast radius:** MLflow only. The HAProxy edit touches one backend
  block; other routes are untouched. Cross-layer: the change spans the
  applications Terraform state (MLflow/proxy) and the infrastructure
  state (HAProxy), so it is applied in two `terraform apply` runs and a
  half-applied change can leave MLflow unreachable or unauthenticated
  between them.
- **Reversibility:** high. Revert the HAProxy backend to
  `192.168.2.50:5050` with the basic-auth line restored, and remove the
  proxy job, to return to today's state.
- **Likeliest failure modes:**
  1. **Multi-issuer trust.** oauth2-proxy is built around a single OIDC
     issuer for the login flow; making it *also* accept Nomad WI bearer
     tokens from a different issuer (skip-jwt-bearer-tokens + extra
     trusted issuer/audience) is the fragile part and may not be
     expressible in one instance. This is the primary technical risk;
     see Q3. It may force a dedicated instance or a second validation
     path.
  2. **Double auth / lockout.** Forgetting to remove `haproxy.hcl:116`
     double-prompts humans and breaks the bearer flow (basic auth has no
     bearer bypass).
  3. **Redirect-URI / host mismatch.** With `network_mode = host` and
     HAProxy rewriting host headers, the OIDC callback URL and cookie
     domain must match `mlflow.localstack`, or the auth-code flow loops.
  4. **Health-check regression.** If the proxy also gates `/health`, the
     Consul check fails and Nomad reschedules the job.
  5. **TLS assumption.** OIDC over plain HTTP:80 means cookies/tokens
     cross the LAN unencrypted; acceptable only as a documented interim
     state (Q4).

## 10. Subtickets

Ordered, dependency-aware.

1. **Confirm L1 landed and pick the deployment shape.** Verify the L1
   oauth2-proxy pattern exists and resolve Q1/Q2 (dedicated vs shared,
   which layer/host owns the proxy). Blocks everything. Depends on:
   nothing (but gated on operator answers).
2. **Provision the OIDC client + cookie secret in Vault.** Add the
   `random_password` + `vault_kv_secret_v2` resources, mirroring
   `secrets.tf:32-44` / `secrets.tf:53-67`. Depends on: 1, and F2 (Vault
   OIDC provider) being able to register the client.
3. **Add the oauth2-proxy task/job** with Vault-templated config for the
   human auth-code flow, upstream `127.0.0.1:5050`, and `/health`
   skip-auth. Depends on: 1-2.
4. **Wire machine bearer validation.** Configure the proxy to accept
   Nomad WI bearer JWTs (trusted issuer/JWKS, expected `aud`) and define
   the non-default Nomad `identity` block a pushing job uses (contrast
   `nomad.hcl.j2:42-45`). Depends on: 3; carries the Q3 risk.
5. **Repoint HAProxy and drop basic auth.** Edit `haproxy.hcl:116-117`.
   Depends on: 3 (proxy must be listening first).
6. **Write the caveat doc + update the reverse-proxy doc.** Depends on:
   3-5.
7. **Run gates + acceptance + adversarial review.** `just pre_commit`,
   the seven live evals, then the review sub-agent. Depends on: 1-6.

## 11. Open questions

Settle Q1-Q4 before the loop runs; Q5-Q6 can be settled during.

- **Q1 — Has L1 landed, and does it ship a reusable oauth2-proxy
  job/module R1 consumes?** No oauth2-proxy exists in the repo today
  (tree-wide search: only the S1 plan matches). *Recommendation:* treat
  L1 as a hard blocker — R1 consumes the L1 pattern and does not
  re-invent it. If L1 is not merged, stop and surface it.
- **Q2 — Dedicated oauth2-proxy for MLflow, or a shared instance with an
  MLflow client?** The epic offers both. *Recommendation:* a
  **dedicated** instance as a sidecar task inside
  `mlflow.hcl` (same group, `network_mode = host` on 192.168.2.50, owned
  by the applications layer). It keeps the redirect-URI/cookie-domain
  local, avoids a shared single point of failure for the first rollout,
  and keeps the change in one Terraform state. Revisit sharing once a
  second service is onboarded.
- **Q3 — Can one oauth2-proxy instance do BOTH Vault-OIDC login AND
  Nomad-WI bearer validation, given two different issuers?** This is the
  load-bearing technical fork. *Recommendation:* prototype
  `--skip-jwt-bearer-tokens` with Nomad's JWKS as an additional trusted
  issuer and the login flow bound to Vault; if a single instance cannot
  trust both, fall back to a dedicated bearer-validation path (or accept
  Nomad WI tokens minted with the Vault-OIDC audience). Do not silently
  narrow the requirement to humans-only — the keyless-machine path is a
  named success criterion.
- **Q4 — Is TLS in scope for R1?** HAProxy binds only `*:80` today
  (`haproxy.hcl:49`); the epic says "behind TLS" but no TLS exists.
  *Recommendation:* deliver R1 over HTTP:80 as an explicit interim state
  and file TLS termination as a separate edge ticket, since adding
  certs/`bind :443` is a cross-cutting change to every route, not
  MLflow-specific. Document the unencrypted-cookie caveat.
- **Q5 — Keep MLflow's LAN firewall rule opening 5050?**
  `services.tf:58-65` allows the whole LAN to reach 5050 directly,
  bypassing the proxy. *Recommendation:* tighten it to allow only the
  proxy/HAProxy host once the proxy is verified, but do it as a
  follow-up so a proxy misconfig does not lock out debugging. Surface,
  do not fold in silently.
- **Q6 — Where does the caveat doc live?** *Recommendation:*
  `docs/mlflow_oauth2_proxy.md` at the `docs/` root, matching the
  existing `docs/haproxy_reverse_proxy.md` topic-doc convention. Operator
  confirm.

## Resolved forks (operator, 2026-07-23)

- **Q1 → L1 hard blocker.** R1 consumes the L1 oauth2-proxy pattern; if
  L1 is not merged, stop and surface.
- **Q2 → Dedicated oauth2-proxy sidecar in `mlflow.hcl`** (revised).
  Operator initially picked "shared," but the cross-ticket
  reconciliation (see below) settled on **dedicated per service +
  reverse-proxy** across L1/R1/R4. So R1 runs its own oauth2-proxy
  sidecar (same group, `network_mode=host` on 192.168.2.50, applications
  layer), proxying to MLflow.
- **Q3 → Prototype a single instance trusting both issuers.** Try
  `--skip-jwt-bearer-tokens` with Nomad's JWKS as an additional trusted
  issuer and login bound to Vault-OIDC. If one instance cannot trust
  both, fall back to a dedicated bearer-validation path or accept
  Nomad-WI tokens minted with the Vault-OIDC audience. The keyless-machine
  path is a REQUIRED success criterion — do not narrow to humans-only.
- **Q4 → TLS-consistent: depend on F3, `--cookie-secure=true`** (revised
  from the planner's HTTP-interim). Aligns with the HTTPS-everywhere
  decision (F2-Q2, L1-Q7). R1 depends on L1, which depends on F3, so TLS
  exists by the time R1 rolls out. No unencrypted-cookie interim.
- **Q5 → Tighten port 5050 NOW, within R1** (revised from follow-up).
  Close direct LAN access to MLflow:5050 so all access goes through the
  proxy. CAVEAT: this removes the direct-port fallback — if the proxy
  misconfigures, debug MLflow via the Nomad alloc / node (Tailscale SSH),
  not the port. Verify the proxy works in the same apply.
- **Q6 → `docs/rfcs/`** (revised from `docs/` root), consistent with the
  S1 doc location.

**Architecture reconciliation (operator, 2026-07-23):** oauth2-proxy is
**dedicated per service + reverse-proxy mode** across L1 (dash), R1
(mlflow), and R4 (phoenix) — one small inline proxy per app, no shared
instance, no HAProxy SPOE/Lua forward-auth. Chosen over shared+forward-auth
for the lighter wiring and per-service blast radius.

**Dependencies:** R1 depends on **L1** (pattern) → **F2** + **F3**.
