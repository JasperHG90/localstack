+++
epic = "rollout"
depends_on = ["L1-landing-oauth2-proxy"]
priority = 5
+++

R4-rollout-phoenix-oauth2-proxy: front the Phoenix web UI with oauth2-proxy against Vault OIDC while leaving OTLP trace ingest working

## 1. Title

Put the Arize Phoenix **web UI** behind oauth2-proxy (Vault OIDC as the
human IdP, reusing the L1 forward-auth pattern), routed via HAProxy, so
that a browser must complete a Vault login to reach the Phoenix console
— **without** breaking OTLP trace ingest from services, which shares
port 6006 (HTTP `/v1/traces`) with the UI and also listens on gRPC 4317.
Only the UI gets oauth2-proxy; ingest does not go through the human
auth-code flow.

## 2. Size / Effort

**Medium.** The moving parts are small (one oauth2-proxy deployment
following L1, one HAProxy backend rewrite, one Vault OIDC client added
in F2's stack, and a path/port split so ingest survives). Effort is
driven not by line count but by three couplings the implementer must get
right: (a) the UI and the HTTP OTLP collector share **one port (6006)**,
so a naive "front 6006 with oauth2-proxy" breaks `memex` trace ingest;
(b) R4 sits on two tickets that are **not yet implemented** (L1, F2 — see
Open Questions Q1/Q2); (c) the auth-code flow runs over the LAN's
plaintext HTTP today, not TLS. The functional success criteria are an
operator manual-acceptance step, not a loop-runnable test.

## 3. Triggered by

Home-lab auth epic. CONFIRMED: **Vault is the OIDC provider for humans**
(Zitadel dropped); Nomad Workload-Identity JWTs are machine identity.
Phoenix has **no native OIDC**, so — as with MLflow (R1) — the UI is
fronted by oauth2-proxy using the L1 forward-auth pattern and a Phoenix
client in Vault's OIDC provider (F2). This is the per-service rollout
step R4 for Phoenix.

## 4. Context

Today's deployed state (all anchors resolved in-repo; re-open these, do
not re-guess):

- **Phoenix job — note: it is under `applications/`, not
  `infrastructure/`** as the epic brief stated. The job is
  `deployments/applications/services/phoenix.hcl`, rendered by
  `deployments/applications/services.tf:97-107` with `phoenix_host =
  "192.168.2.29"` (`services.tf:103`). It pins the mutable tag
  `docker.io/arizephoenix/phoenix:latest` (`phoenix.hcl:53`), runs
  `network_mode = "host"` on `orangepi4a` (constraint
  `phoenix.hcl:6-9`), and exposes **two static ports**:
  - `http = 6006` (`phoenix.hcl:12-14`) — the **web UI AND the HTTP
    OTLP collector** (`/v1/traces`) are the same port. Registered as
    Consul service `phoenix` with an HTTP `/healthz` check
    (`phoenix.hcl:23-36`).
  - `grpc = 4317` (`phoenix.hcl:15-17`) — the gRPC OTLP ingest
    endpoint. Registered as Consul service `phoenix-grpc` with a TCP
    check (`phoenix.hcl:38-50`).
- **The port-6006 collision is the load-bearing fact.** `memex` sends
  traces over HTTP OTLP to
  `http://${phoenix_host}:6006/v1/traces`
  (`deployments/applications/services/memex.hcl:143`). It is the only
  in-repo OTLP sender to Phoenix (repo-wide grep for `6006` / `4317` /
  `v1/traces` finds only `memex.hcl:143` plus the Phoenix job and the
  HAProxy backend). Nothing in-repo sends to gRPC 4317, but the port is
  exposed for external/dev senders. **If all of :6006 is placed behind
  the browser auth-code flow, `memex` ingest breaks** — this is exactly
  the UI-vs-ingest distinction the epic calls out, on a single port.
- **HAProxy edge**, `deployments/infrastructure/services/haproxy.hcl`,
  runs on `firebat` and binds **plaintext `*:80`** (`haproxy.hcl:49`) —
  there is **no TLS / port 443 / SSL cert anywhere** (grep confirms).
  Phoenix is routed by host ACL `phoenix.localstack`
  (`haproxy.hcl:56`, `use_backend` at `:69`) to backend `phoenix`
  (`haproxy.hcl:99-101`), which **currently applies HTTP basic auth**:
  `http-request auth unless { http_auth(openfang_users) }`
  (`haproxy.hcl:100`) against the `openfang_users` userlist
  (`haproxy.hcl:45-46`), then proxies to `192.168.2.29:6006`
  (`haproxy.hcl:101`). MLflow (`haproxy.hcl:115-117`) and Bifrost
  (`:119-121`) use the same basic-auth line today. The
  `openfang_password` is injected at
  `deployments/infrastructure/services.tf:309-313`.
- **Dependency L1 (oauth2-proxy forward-auth pattern) is not yet in the
  repo.** No `oauth2-proxy` job, forward-auth config, or L1 ticket file
  exists (`ls .loop/plans/` shows only F2, M1, S1-S3; repo-wide grep for
  `oauth2-proxy` outside `.cache` returns only ticket prose). R4 **reuses
  a pattern that L1 must first establish** — see Q1.
- **Dependency F2 (Vault OIDC provider) is scoped but not applied.** Its
  ticket `.loop/plans/F2-foundation-vault-oidc-provider.md` creates the
  issuer + clients in a new `deployments/infrastructure/oidc.tf`, but its
  declared clients are **oauth2-proxy (landing page, L1) + three MinIO
  tiers** (F2 §6, lines 99-102) — **there is no Phoenix client yet**, and
  F2's issuer is plaintext-HTTP with `https_enabled = false` (F2 Q2). R4
  needs a Phoenix OIDC client (or to reuse L1's shared client) — see Q3.

What is missing: an oauth2-proxy fronting the Phoenix UI, a Phoenix OIDC
client in Vault, and a HAProxy routing change that authenticates browser
paths while leaving OTLP ingest (both the `/v1/traces` HTTP path on 6006
and gRPC 4317) reachable by services.

## 5. Non-goals / out of scope

- **Not** authenticating OTLP trace ingest through the browser
  auth-code flow. gRPC (4317) must never be routed through oauth2-proxy
  (it would break the gRPC stream), and the HTTP OTLP path
  (`/v1/traces` on 6006) must not require an interactive login. R4
  either leaves ingest unauthenticated on the trusted LAN or gates it
  with a non-interactive Bearer/mTLS mechanism — a decision to make and
  document, not route through forward-auth (see Q4).
- **Not** building the oauth2-proxy forward-auth pattern itself (that is
  L1) or the Vault OIDC issuer/scope/key (that is F2). R4 consumes both.
- **Not** rolling MLflow, Bifrost, or any other service behind
  oauth2-proxy (those are R1 / their own R-tickets). R4 touches Phoenix
  and its HAProxy backend only.
- **Not** changing where Phoenix runs, its image, its Postgres backing
  (`phoenix.hcl:59-66`), or its ports.
- **Not** terminating TLS at HAProxy or changing the `*:80` listener.
  If oauth2-proxy or Vault demands an `https` issuer/cookie, that TLS
  work is a separate cross-cutting ticket (see Q5), consistent with F2
  Q2.
- **Not** repointing `memex`'s tracing endpoint away from `/v1/traces`
  unless Q4's chosen option requires it (default recommendation does
  not touch `memex.hcl:143`).

## 6. Requirements & restrictions

Must achieve:

- Browsing `http://phoenix.localstack` requires a completed Vault OIDC
  login via oauth2-proxy; an unauthenticated browser is redirected to
  the Vault login and cannot reach the Phoenix console.
- OTLP trace ingest continues to work: `memex`'s
  `http://192.168.2.29:6006/v1/traces` POSTs
  (`memex.hcl:143`) still succeed, and gRPC 4317 is untouched by
  HAProxy/oauth2-proxy.
- The pre-existing HAProxy basic-auth on the Phoenix backend
  (`haproxy.hcl:100`) is **replaced**, not stacked on top of
  oauth2-proxy (no double auth). Remove only the Phoenix line; leave
  MLflow/Bifrost basic-auth lines untouched (surgical change).
- The OTLP-ingest auth posture (Q4) is **explicitly documented** in the
  job/HAProxy config or a short doc note, per the epic's instruction to
  "decide and document."

Restrictions the repo enforces (cited):

- **Reuse the L1 pattern; do not invent a new one.** R4 must follow
  whatever oauth2-proxy shape L1 establishes (central forward-auth vs
  per-service sidecar). "Match existing style… no abstractions for
  single-use code" (`CLAUDE.md` §2, §3). If L1 is not yet merged, R4 is
  blocked or must be authored against L1's agreed shape (Q1).
- **Surface tradeoffs, do not pick silently** (`CLAUDE.md` §1). The
  port-6006 split, the ingest-auth posture, TLS, and the OIDC-client
  ownership are forks recorded in §11, not decided here.
- **Secrets live in Vault KV2, never hardcoded** (`CLAUDE.md` Key
  Conventions; pattern at
  `deployments/infrastructure/secrets.tf:10-29`). The oauth2-proxy
  `client_secret` and `cookie_secret` must come from Vault via a
  `template { … }` block (as `phoenix.hcl:59-66` and `mlflow.hcl:47-56`
  template DB creds), never committed. `detect-private-key` runs in
  pre-commit (`.pre-commit-config.yaml`).
- **Provider/version pins are authoritative.** The oauth2-proxy image
  must be pinned to a specific tag (not `latest`) even though the
  Phoenix job itself uses `:latest` — do not copy that anti-pattern into
  new config.
- **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`):
  hand a sub-agent the port-6006 ingest-survival check specifically.

## 7. Code surface

Exact files and anchors, each with the change:

- **`deployments/infrastructure/services/haproxy.hcl:99-101`** — the
  `backend phoenix` block. Replace the basic-auth line (`:100`) with the
  L1 forward-auth mechanism (e.g. `http-request auth` replaced by an
  oauth2-proxy `forward-auth`/`use_backend` to the oauth2-proxy
  frontend), **scoped to browser paths only**. The OTLP HTTP path
  (`/v1/traces`, and any `/v1/*` collector path) must bypass auth (an
  ACL exempting it, or a separate unauthenticated backend to
  `192.168.2.29:6006`). Confirm the exact split against Q4's chosen
  option. Server target stays `192.168.2.29:6006`.
- **oauth2-proxy deployment (shape per L1)** — either a new
  `deployments/applications/services/phoenix-oauth2-proxy.hcl` (+ a
  `nomad_job` in `deployments/applications/services.tf` near the Phoenix
  block at `:96-107`) if L1 uses per-service oauth2-proxy, or a config
  entry in L1's central oauth2-proxy if L1 is centralized. Do **not**
  author this until Q1 settles L1's shape. It must template
  `client_id` / `client_secret` / `cookie_secret` from Vault KV2 and set
  the Vault OIDC issuer, redirect URL `http://phoenix.localstack/…`
  (path per L1), and the allowed group (Q6).
- **`deployments/applications/services/memex.hcl:143`** — READ, cited.
  Its `…:6006/v1/traces` endpoint is the ingest that must not break.
  Edited **only if** Q4's chosen option repoints it (default: not
  touched).
- **F2's `deployments/infrastructure/oidc.tf`** (created by F2) — add a
  Phoenix `vault_identity_oidc_client` + its `assignment` + a
  `vault_kv_secret_v2` for the client secret, following F2 §7 and
  `secrets.tf:15-29`. This is a **coordination edit into F2's file**
  (Q3): either R4 adds it, or F2 is extended to include a `phoenix`
  client. Decide ownership before writing.

Reference anchors the implementer will re-open: `phoenix.hcl:6-9,12-17,
23-50`, `services.tf:97-107`, `haproxy.hcl:45-46,49,56,69,99-101,309`
(note `:309` is in `infrastructure/services.tf`, not the job),
`memex.hcl:143`, F2 ticket §6-§7.

## 8. Tests & validation gates

This ticket ships HCL + Terraform, no Python — the "every code change
ships a test" constraint (`.claude/rules/python-testing.md`) has no unit
to exercise here. Two gates apply: the repo's pre-commit run (now
Terraform-aware) and a now-runnable live acceptance eval.

### Repo gate (the loop's gate): `just pre_commit`

`just pre_commit` → `pre-commit run --all-files` (root `justfile:17-18`)
is the single loop gate and now validates **both** `.hcl` and `.tf`.
Configured hooks (`.pre-commit-config.yaml`):

- Upstream hooks: `check-json`, `check-ast`, `check-merge-conflict`,
  `check-yaml --unsafe`, `debug-statements`, `detect-private-key`,
  `end-of-file-fixer` (`.pre-commit-config.yaml:6-13`).
- Local `nomad-fmt` — `nomad fmt -recursive`, scoped to `.hcl`
  (`types: [hcl]`, `.pre-commit-config.yaml:16-21`). Every new/edited
  `.hcl` (the oauth2-proxy job, the HAProxy job) is `nomad fmt`-checked.
- Local `terraform-fmt` — `terraform fmt -check -recursive`,
  `types: [terraform]` (`.pre-commit-config.yaml:22-27`).
- Local `terraform-validate` — `scripts/tf_validate.sh`,
  `types: [terraform]` (`.pre-commit-config.yaml:28-33`). The script
  runs `terraform validate` against all three roots
  (`deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`) offline with
  `init -backend=false`, so it needs no Consul backend or credentials
  (`scripts/tf_validate.sh:7-19`).

Because `terraform-fmt` and `terraform-validate` run **inside**
`just pre_commit`, the `.tf` edits this ticket makes (the `nomad_job`
for oauth2-proxy and/or F2's `oidc.tf`) are formatted and validated by
the loop gate itself. There is **no separate `terraform fmt` /
`terraform validate` step to run by hand** — the earlier "terraform not
validated by pre-commit" caveat no longer holds. The config `exclude`
is `^\.(claude|loop)/` (`.pre-commit-config.yaml:1`), so this ticket
file is not linted, and `detect-private-key` plus the KV2 convention
forbid committing the oauth2-proxy client/cookie secrets in the diff.

**The loop's verifiable bar is a green `just pre_commit`.**

### Evals (live acceptance)

The cluster is reachable from this environment — `VAULT_ADDR`,
`VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are
all set — so the two R4 success criteria are **runnable** after the
change is applied, not deferred to a manual step. Run all three checks
below once `terraform apply` and the Nomad deploy have landed. They
**depend on L1 (the oauth2-proxy pattern) and F2 (the Vault OIDC
provider) being applied first** (Open Questions Q1/Q2); until both land
there is no auth backend for the UI check to redirect to.

Both sides of the port-6006 collision must be evaluated together. A pass
requires the UI check to gate **and** both ingest checks to stay
ungated. Breaking either side is a fail.

**(a) UI is gated** — an unauthenticated request is redirected to the
Vault OIDC login instead of the Phoenix console:

```
curl -sI https://phoenix.localstack/
```

Expected: a `302` whose `Location` points at the Vault OIDC login
(`vault.localstack` / the oauth2-proxy `/oauth2/start` sign-in), **not**
a `200` that serves the Phoenix app. A `200` means the console is
reachable unauthenticated — a fail.

**(b) HTTP OTLP ingest still works and is NOT gated** — this is the
`memex` ingest path (`memex.hcl:143`) that must survive the split:

```
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  http://192.168.2.29:6006/v1/traces \
  -H 'content-type: application/json' \
  -d '{"resourceSpans":[]}'
```

Expected: a **non-auth** status returned by Phoenix's collector itself —
`200`, `415`, or a `400`/parse error depending on the payload — which
proves the request reached Phoenix. It must **not** be `302` or `401`:
either means oauth2-proxy intercepted the ingest path and `memex` trace
ingest is broken. This is the highest-value check in the ticket.

**(c) gRPC OTLP ingest (4317) is still reachable** and never routed
through HAProxy/oauth2-proxy (services reach `192.168.2.29:4317`
directly):

```
nc -z -w3 192.168.2.29 4317 && echo "4317 open"
```

Expected: the port is open (`4317 open`). If `nc` is unavailable, use
`timeout 3 bash -c '</dev/tcp/192.168.2.29/4317' && echo "4317 open"`.
R4 must leave this path unchanged.

Record the outputs of (a), (b), and (c) at close-out. The port-6006
ingest-survival evidence ((b) and (c)) is the specific item to hand the
adversarial reviewer (`.claude/rules/adversarial-reviews.md`).

These live-acceptance scenarios are captured as the loop eval marker at
`.loop/evals/R4-rollout-phoenix-oauth2-proxy.md` (six rows: job-status, UI
gated, HTTP `/v1/traces` ungated, gRPC 4317 reachable, no double-auth, and a
reviewer-judged authenticated-render check).

## 9. Risk assessment

- **Blast radius (loop-time):** near zero — the loop only edits config
  and never applies. **Blast radius (apply-time, operator):** medium.
  Getting the port-6006 split wrong silently breaks `memex` trace ingest
  (data loss for observability) while the UI still looks fine — the
  highest-value failure to guard against. A too-broad auth rule locks
  ingest out; a too-narrow one leaves the UI reachable unauthenticated.
- **Reversibility:** high. Reverting the HAProxy backend to the
  basic-auth line (`haproxy.hcl:100`) and removing the oauth2-proxy job
  restores today's behavior; no data migration.
- **Likeliest failure modes:** (1) fronting all of :6006 and breaking
  `memex.hcl:143` ingest (mitigate: path-exempt `/v1/traces`, test it);
  (2) building against an L1 pattern that does not exist yet, so R4's
  oauth2-proxy shape diverges from the eventual L1 (mitigate: block on
  Q1); (3) F2 has no Phoenix client, so the auth-code flow has no valid
  `client_id`/redirect (mitigate: Q3 coordination); (4) oauth2-proxy
  rejecting the plaintext-HTTP Vault issuer or refusing to set an
  insecure cookie over `http://` (mitigate: Q5, `--cookie-secure=false`
  for v1, mirrors F2 Q2); (5) double auth if the basic-auth line is left
  in place alongside oauth2-proxy.

## 10. Subtickets (ordered, dependency-aware)

1. **Settle the forks (blocking).** Operator answers Q1 (L1 shape +
   readiness), Q3 (Phoenix OIDC client ownership), Q4 (ingest-auth
   posture), Q5 (http vs https / cookie), Q6 (which group gates Phoenix).
   Nothing below can be authored correctly until these are set.
2. **Add the Phoenix OIDC client** in F2's `oidc.tf`
   (`vault_identity_oidc_client` + assignment + `vault_kv_secret_v2` for
   the secret), redirect URI per L1's callback path. `terraform validate`.
3. **Deploy oauth2-proxy for Phoenix** following L1's pattern
   (new `.hcl` + `nomad_job`, or L1 central-config entry), templating
   client/cookie secrets from Vault, issuer = Vault OIDC, allowed group
   from Q6. `nomad fmt`.
4. **Rewrite the HAProxy Phoenix backend** (`haproxy.hcl:99-101`):
   forward-auth for browser paths, **exempt `/v1/traces` (and OTLP HTTP
   collector paths)** per Q4, remove the basic-auth line, keep the
   `:6006` server. Leave MLflow/Bifrost lines untouched. `nomad fmt`.
5. **Document the ingest-auth decision** (Q4) inline in the config
   and/or a short note under `docs/` (if a doc is added, it is subject to
   `end-of-file-fixer` and the slop scan,
   `.claude/rules/slop-scan-for-docs.md`).
6. **Gate + adversarial review.** Run `just pre_commit`, `terraform
   fmt`/`validate`; hand a reviewer the port-6006 ingest-survival check
   (`.claude/rules/adversarial-reviews.md`). Record the operator
   acceptance procedure (§8) in close-out.

## 11. Open questions (forks — operator must settle)

- **Q1 — L1 does not exist yet (BLOCKING).** No oauth2-proxy job,
  forward-auth config, or L1 ticket is in the repo. R4 reuses L1's
  pattern, so its central-vs-per-service shape and callback path are
  undefined. *Recommendation:* treat R4 as **blocked on L1 merging**;
  the "per-service rollout" framing suggests a per-service oauth2-proxy
  (a sidecar/job fronting `localhost:6006` on `orangepi4a`), so author
  R4 against that shape but do not implement until L1 lands and fixes the
  callback path. If the operator wants R4 authored in parallel, pin the
  assumed L1 shape here first.
- **Q2 — F2 not yet applied.** F2 (`.loop/plans/F2-…md`) is scoped but
  its `oidc.tf` is not in the tree. R4's OIDC client depends on F2's
  issuer/scope/key existing. *Recommendation:* sequence R4 after F2
  apply; if authored earlier, reference F2's resource names as the
  contract.
- **Q3 — Who owns the Phoenix OIDC client?** F2's declared clients are
  oauth2-proxy-landing-page + three MinIO tiers — no Phoenix client.
  Does R4 add a dedicated `phoenix` client to F2's `oidc.tf`, or does one
  shared oauth2-proxy client cover all fronted UIs (if L1 is a single
  central landing page)? *Recommendation:* if L1 is per-service, add a
  dedicated `phoenix` `vault_identity_oidc_client` (redirect
  `http://phoenix.localstack/oauth2/callback`, path per L1) in F2's
  `oidc.tf` and a `vault_kv_secret_v2` for its secret; if L1 is central,
  reuse the single client and register `phoenix.localstack` as an allowed
  redirect. Confirm L1's model first (ties to Q1).
- **Q4 — OTLP ingest auth posture (the epic asks to decide+document).**
  The HTTP OTLP collector shares port 6006 with the UI, and gRPC ingest
  is on 4317. *Recommendation:* for v1, **leave ingest unauthenticated on
  the trusted LAN**: at HAProxy, exempt `/v1/traces` (and OTLP HTTP
  collector paths) from oauth2-proxy so `memex.hcl:143` keeps working,
  and leave gRPC 4317 entirely off the HAProxy path (services reach
  `192.168.2.29:4317` directly). This keeps R4 UI-only and does not touch
  `memex.hcl:143`. A Bearer-token or mTLS gate on ingest is a documented
  **follow-up**, not R4. The alternative — repointing `memex` to gRPC
  4317 and fully guarding 6006 — expands scope into `memex` config and is
  not recommended.
- **Q5 — http vs https / cookie security.** HAProxy binds plaintext
  `*:80` (`haproxy.hcl:49`) and Vault's issuer is `http://`
  (F2 Q2). oauth2-proxy defaults to a secure cookie and may reject a
  non-https issuer. *Recommendation:* v1 runs over `http` on the trusted
  LAN with `--cookie-secure=false` and `--insecure-oidc-*` as needed;
  record that a real fix is TLS termination at HAProxy for
  `phoenix.localstack` (and `vault.localstack`), a separate cross-cutting
  ticket — the epic brief's "behind TLS" phrasing does **not** match the
  current plaintext edge and should not be silently assumed.
- **Q6 — Which Vault identity group may access the Phoenix UI?** F2
  defines `minio-admins/readers/writers` and `dashboard-users`
  (F2 §6). *Recommendation:* gate Phoenix on `dashboard-users` (the F2
  group intended for observability dashboards) via oauth2-proxy's
  allowed-group setting; if the operator wants Phoenix access decoupled
  from Grafana/other dashboards, add a dedicated `phoenix-users` group in
  F2 instead. Confirm before wiring the assignment.

## Resolved forks (operator, 2026-07-23)

- **Q1 → Blocked on L1; per-service dedicated proxy.** Per the locked
  architecture (dedicated + reverse-proxy across L1/R1/R4), R4 is a
  dedicated `phoenix` oauth2-proxy fronting `localhost:6006` on
  `orangepi4a`. Author against that shape; do not implement until L1
  lands.
- **Q2 → Sequence after F2 apply.** R4's OIDC client depends on F2's
  issuer/scope/key. Reference F2 resource names as the contract if
  authored earlier.
- **Q3 → Dedicated `phoenix` OIDC client in F2's `oidc.tf`** (+ a
  `vault_kv_secret_v2` for its secret), redirect
  `https://phoenix.localstack/oauth2/callback` (https per Q5).
  CROSS-CUTTING: because the architecture is dedicated-per-service, F2
  must provision one oauth2-proxy OIDC client PER fronted service —
  `dash` (L1), `mlflow` (R1), `phoenix` (R4) — not just the
  landing-page + MinIO-tier clients originally scoped. See the note fed
  back into F2.
- **Q4 → UI-only gate; ingest unauthenticated on the LAN.** Exempt
  `/v1/traces` (+ OTLP HTTP paths) from oauth2-proxy at HAProxy so
  `memex.hcl:143` keeps working; leave gRPC 4317 off the HAProxy path.
  Bearer/mTLS on ingest is a documented follow-up, not R4.
- **Q5 → TLS-consistent: F3 + `--cookie-secure=true`** (revised from the
  planner's http/insecure v1). Aligns with HTTPS-everywhere
  (F2/F3/L1/R1). https issuer, depend on F3 for `phoenix.localstack`
  TLS; no cleartext-cookie interim.
- **Q6 → Reuse `dashboard-users`.** Gate Phoenix on F2's existing
  `dashboard-users` group via oauth2-proxy's allowed-group. No dedicated
  `phoenix-users` group.

**Dependencies:** R4 depends on **L1** (pattern) → **F2** (OIDC client,
`dashboard-users` group) + **F3** (TLS).
