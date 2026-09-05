---
epic = "bifrost"
depends_on = []
priority = 60
summary = "Front Bifrost's dashboard UI and admin API with a dedicated oauth2-proxy instance (port 4181, same node) authenticating humans against Vault's lab OIDC provider at the edge. Inference paths /v1/* and /anthropic/* skip the cookie gate and stay on virtual keys. Bifrost's native admin auth stays on (double login accepted). Direct-to-node consumers (Hermes, Memex, Prometheus, the Terraform bifrost provider) are untouched."
tags = ["bifrost", "oauth2-proxy", "oidc", "vault", "haproxy", "terraform"]
---

# Ticket: B2-bifrost-oauth2-proxy

## 1. Title

Deploy a Bifrost-scoped oauth2-proxy so a browser hitting
`https://bifrost.lab.orangecluster.nl` must complete a Vault OIDC login,
while machine inference through `/v1/*` and `/anthropic/*` keeps using
virtual keys with no cookie gate.

## 2. Size / Effort

**Small-Medium.** One new jobspec (a close copy of L1's
`oauth2-proxy.hcl`), one Vault OIDC client plus the one unavoidable
shared-locals edit, two KV secrets, one `nomad_job` resource, one
firewall rule, one HAProxy backend line repointed, one doc update. All
in the infrastructure root. No application code, no change to
`bifrost.hcl` or the applications root. What drives it past Small: the
skip-auth regex semantics must be verified against the real v7.13
container (P10), and the HAProxy repoint flips all edge traffic in one
line.

## 3. Triggered by

Home-lab auth epic, Bifrost's human-access step. B1 (done) gave Bifrost
native admin auth and virtual keys but left the edge pass-through: any
LAN browser reaches the dashboard login page and the admin API
unauthenticated at the edge. Operator settled the design 2026-09-03:

1. **Per-app oauth2-proxy instance** — the pattern L1 established for
   dash and SY1 Requirement 6 approved for switchyard. NOT a shared
   instance, NOT HAProxy forward-auth. DECIDED.
2. **skip-auth routes: exactly `/v1/*` and `/anthropic/*`.** On skipped
   paths Bifrost's own `enforce_auth_on_inference` + virtual keys remain
   the auth. No `/health` skip needed: the Consul check, the Terraform
   readiness poll, and the bifrost provider all hit
   `192.168.2.50:8080` directly, never the edge (P2). DECIDED.
3. **Bifrost's native admin auth stays on.** Double login (Vault OIDC
   at the edge, then Bifrost admin password) is accepted. Do NOT attempt
   header or basic-auth injection. DECIDED.

## 4. Context

Verified 2026-09-03 against this checkout.

- Bifrost: `deployments/applications/services/bifrost.hcl` — host
  network, static port 8080 (`:11-15`), pinned to node radxa-dragon-q6a
  (`:6-9`), Consul service `bifrost` at address `${bifrost_host}` =
  192.168.2.50 with a GET `/health` check (`:20-37`). Admin creds from
  Vault KV `default/bifrost/credentials` via env template (`:62-65`);
  `config.json` sets `client.enforce_auth_on_inference = true`
  (`:98-102`) and `governance.auth_config.is_enabled = true`
  (`:103-109`). Rendered by
  `deployments/applications/services.tf:502-530` (version pin 1.6.7 at
  `:508`).
- Terraform's machine path to Bifrost is direct, not via the edge:
  `null_resource.bifrost_ready` polls `http://192.168.2.50:8080/health`
  (`deployments/applications/services.tf:552-555, :561`), and
  `provider "bifrost"` reads that same endpoint trigger
  (`deployments/applications/providers.tf:59-70`), gating
  `bifrost_virtual_key.hermes` / `.memex`
  (`deployments/applications/services.tf:580-603`).
- HAProxy edge: `deployments/infrastructure/services/haproxy.hcl` —
  `acl is_bifrost` (`:106`), `use_backend bifrost` (`:118`),
  `backend bifrost` is a bare pass-through to `192.168.2.50:8080`
  (`:175-176`). No auth line since B1. `backend dash` (`:178-179`)
  already shows the target shape: edge to a proxy port on the same node
  (`192.168.2.50:4180`).
- Direct consumers that bypass the edge today: Hermes calls
  `http://127.0.0.1:8080/v1` on the shared node (`hermes.hcl:158`);
  Memex calls `http://192.168.2.50:8080/v1` (`memex.hcl:168, :175,
  :178`); Prometheus scrapes `192.168.2.50:8080/metrics` with basic
  auth (`deployments/infrastructure/services/prometheus.hcl:129-135`).
- L1 precedent to copy:
  `deployments/infrastructure/services/oauth2-proxy.hcl` — v7.13.0
  (`:95`), host network port 4180 (`:35-39`), same node (`:30-33`),
  env-only config via a Vault template (`:58-76`), `/ping` check
  (`:83-91`). The header comment (`:10-23`) lists the traps: plural env
  names (`EMAIL_DOMAINS`, `UPSTREAMS`), `PROVIDER=oidc`,
  `HTTP_ADDRESS` binds 0.0.0.0, `OIDC_EMAIL_CLAIM=sub` when only
  `openid` is requested, `REVERSE_PROXY` unset because HAProxy sends no
  `X-Forwarded-*`. Wired at
  `deployments/infrastructure/services.tf:465-489`; firewall allows
  only HAProxy (192.168.2.30) to 4180 (`:334-341`).
- Vault OIDC: provider `lab` (`deployments/infrastructure/oidc.tf:117-126`),
  consumer contract at `:92-107` (append your client id to
  `local.oidc_provider_client_ids` — the one shared edit), worked
  consumer example `vault_identity_oidc_client.oauth2_proxy`
  (`:188-211`): confidential, `assignments = ["allow_all"]` (branch 3,
  `docs/vault-human-auth.md:288-292`), redirect URL held in a local so
  registration and jobspec cannot drift (`:183-190`). A client must
  REQUEST every scope it needs or Vault silently drops it
  (`docs/vault-human-auth.md:306-314`). L1 requests `openid` only.
- Secrets shape: `deployments/infrastructure/secrets.tf:206-249` — KV
  `default/oauth2-proxy/oidc` {client_id, client_secret, issuer} plus a
  32-char no-special `random_password` cookie secret (base64url-decode
  length trap documented at `:227-230`).
- Upstream Bifrost (external, verified 2026-09-03 against
  docs.getbifrost.ai and the bifrost repo): OSS has NO native OIDC (SSO
  is enterprise-only), which is why the proxy approach. Admin API
  (`/api/*`) accepts basic auth or a session bearer; virtual keys are
  NOT valid there. Inference accepts `x-bf-vk` / bearer / `x-api-key`.
- Port 4181 appears nowhere in `deployments/` (grep, 2026-09-03).
- The `nomad-workloads` Vault policy grants
  `secret/data/<namespace>/<job_id>/*`
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-5`),
  so the new job's name must prefix its KV path exactly.

What is missing: nothing gates a human at the edge. The Bifrost
dashboard login page and admin API are served to any LAN browser via
`https://bifrost.lab.orangecluster.nl`.

## 5. Non-goals / out of scope

- Header/basic-auth injection to collapse the double login (decision 3).
- Touching `bifrost.hcl`, the bifrost provider wiring, virtual keys, or
  anything in the applications root.
- Changing how Hermes, Memex, or Prometheus reach Bifrost. They bypass
  the edge and stay that way.
- Handling the N4 collision. N4-netsec-edge-only-service-access
  (planning) will close the direct LAN path; when it lands, Memex's and
  Prometheus's direct flows (and `/metrics`, which sits behind the
  cookie gate at the edge) must be rethought THERE. Documented as a risk
  in §9; the relay-finding skill may carry it onto N4.
- Skipping auth for provider prefixes beyond `/v1/*` and `/anthropic/*`
  (see Q3).
- A shared multi-app oauth2-proxy or HAProxy forward-auth (decision 1).
- Group-gated access. Flat `allow_all`, matching L1.

## 6. Requirements & restrictions

Must achieve:

1. An unauthenticated browser request to
   `https://bifrost.lab.orangecluster.nl/` (and any admin/UI path) is
   not served Bifrost content: oauth2-proxy answers with its login
   redirect/page instead.
2. `/v1/*` and `/anthropic/*` through the edge skip the cookie gate and
   reach Bifrost, where `enforce_auth_on_inference` + virtual keys
   still apply (`bifrost.hcl:98-102`). Skip regexes are anchored so
   `/v1foo` does NOT skip (P10).
3. All four direct consumers keep working unchanged: Hermes
   (`hermes.hcl:158`), Memex (`memex.hcl:168`), Prometheus
   (`prometheus.hcl:129-135`), and the Terraform bifrost provider +
   readiness poll (`deployments/applications/providers.tf:59-70`,
   `deployments/applications/services.tf:552-555`).
   Satisfied structurally: none of those files change and port 8080
   stays untouched.
4. Bifrost's `governance.auth_config` stays enabled exactly as B1 left
   it (`bifrost.hcl:103-109` unchanged).
5. The new Vault OIDC client points at provider `lab`, never `default`
   (`oidc.tf:112-116`), uses `assignments = ["allow_all"]`, is
   confidential, and its client id is appended to
   `local.oidc_provider_client_ids` (`oidc.tf:99-107`).
6. The redirect URL
   `https://bifrost.lab.orangecluster.nl/oauth2/callback` is a single
   local consumed by both the client registration and the jobspec var,
   copying `oidc.tf:183-198`.
7. Client secret and cookie secret live in KV2 under the new job's own
   prefix and reach the job via `template { env = true }`. Never a
   `.tf` or jobspec literal (`docs/vault-human-auth.md:315-319`;
   `detect-private-key` does not catch `hvo_secret_...`). KV prefix
   must equal the Nomad job name (P13).
8. Firewall: only HAProxy (192.168.2.30) may reach the new proxy port,
   copying `deployments/infrastructure/services.tf:334-341`.
9. HAProxy `backend bifrost` points at the proxy port, not 8080.

Restrictions the repo enforces:

- Surgical changes only (`CLAUDE.md` §3).
- Plain-language comments, minimal (`.claude/rules/plain-language.md`,
  `.claude/rules/minimal-comments.md`).
- Adversarial review before done
  (`.claude/rules/adversarial-reviews.md`).
- Gates via `just pre_commit` (`justfile:18-19`), which runs
  `nomad fmt`, `terraform fmt -check`, and `scripts/tf_validate.sh`
  (`.pre-commit-config.yaml:16-32`).

## 7. Code surface

All in `deployments/infrastructure/` plus one doc.

- **`deployments/infrastructure/services/oauth2-proxy-bifrost.hcl`
  (NEW)** — copy `oauth2-proxy.hcl` (its header `:10-23` traps apply
  verbatim): static port **4181** (Q2), node radxa-dragon-q6a
  constraint, image `quay.io/oauth2-proxy/oauth2-proxy:v7.13.0`, host
  network, `/ping` Consul check, `HTTP_ADDRESS=0.0.0.0:4181`. Single
  catch-all upstream `http://127.0.0.1:8080` (Bifrost is on the same
  node). New versus L1: `OAUTH2_PROXY_SKIP_AUTH_ROUTES` carrying the
  two anchored regexes (e.g. `^/v1/`, `^/anthropic/` — verify exact
  env name, separator, and anchoring semantics against the container,
  P10). Scope per Q1 (recommend `openid` + `OIDC_EMAIL_CLAIM=sub`,
  copying L1). `REVERSE_PROXY` stays unset; `REDIRECT_URL` given
  explicitly. Job name must equal the KV prefix segment (P13):
  recommend job `oauth2-proxy-bifrost` with KV
  `default/oauth2-proxy-bifrost/{oidc,cookie}`.
- **`deployments/infrastructure/services.tf`** — new
  `nomad_job "oauth2_proxy_bifrost"` beside `:465-489`, threading the
  two KV paths and the redirect-URL local; new firewall rule
  `allow from 192.168.2.30 to any port 4181 proto tcp` beside
  `:337-341` (append to the `oauth2_proxy` entry or add a sibling
  entry, matching local style).
- **`deployments/infrastructure/oidc.tf`** — new
  `vault_identity_oidc_client` + `vault_identity_oidc_key_allowed_client_id`,
  copying `:188-211` (confidential, `allow_all`, TTLs 3600, redirect
  local); append the client id to `local.oidc_provider_client_ids`
  (`:99-107`, the one marked consumer line).
- **`deployments/infrastructure/secrets.tf`** — new KV pair copying
  `:206-249`: `default/oauth2-proxy-bifrost/oidc` {client_id,
  client_secret, issuer} and `default/oauth2-proxy-bifrost/cookie`
  with a 32-char `special = false` `random_password` (decode trap
  `:227-230`).
- **`deployments/infrastructure/services/haproxy.hcl:175-176`** —
  `backend bifrost` server line becomes `192.168.2.50:4181`. Nothing
  else in the file.
- **`docs/haproxy_reverse_proxy.md:23-26`** — bifrost row now lands on
  4181; note the OIDC gate and the skip-auth inference paths.

No Python, no tests directory involvement: the change is Terraform/HCL
only, validated by the gates in §8.

## 8. Tests & validation gates

- **Gate:** `just pre_commit` (`justfile:18-19`) — `nomad fmt`,
  `terraform fmt -check`, `terraform validate` across roots via
  `scripts/tf_validate.sh` (`.pre-commit-config.yaml:16-32`). No other
  test runner applies; the repo has no unit-test suite for the
  deployments tree.
- **Eval:** `.loop/evals/B2-bifrost-oauth2-proxy.md`, to be co-authored
  with the create-eval skill (required: `.loop/config.json` sets
  `require_eval`). Follow B1's precedent
  (`.loop/archive/B1-bifrost-native-auth-and-virtual-keys/eval.md`):
  static, deterministic assertions against the rendered HCL/TF — no
  `terraform apply` by the loop. Load-bearing rows: skip-auth env
  present with anchored regexes; upstream is loopback 8080; backend
  bifrost is `:4181`; `bifrost.hcl` unchanged (`git diff` empty);
  client id appended to `local.oidc_provider_client_ids`; firewall rule
  present; no secret literal in any `.tf`/rendered jobspec.
- Live checks (operator, post-apply, recorded in the eval as manual
  rows if kept): edge `/` redirects to Vault; edge `/v1/chat/completions`
  without a cookie returns Bifrost's own 401 (virtual-key refusal), not
  a proxy redirect; a virtual-key call through the edge succeeds;
  Consul check `oauth2-proxy-bifrost ping` green.

## 9. Risk assessment

- **Blast radius: the edge path only.** One HAProxy line flips all
  `bifrost.lab` traffic to the proxy. Direct consumers (all four
  machine paths) never touch the edge, so inference and Terraform
  cannot break — provided `bifrost.hcl` and port 8080 stay untouched,
  which §6.3 makes binding.
- **Reversibility: high.** Revert the backend line and the edge is
  back to pass-through; the proxy job can idle or be removed.
- **Likeliest failure: skip-auth regex semantics.** Unanchored or
  mis-separated regexes either leave inference cookie-gated (breaks
  external tool clients) or skip too much (exposes admin paths). P10
  marks the exact v7.13 behavior for container verification, the same
  way L4 settled the upstream-matching question.
- **Dashboard websocket.** Bifrost's live log tail may use `/ws`
  (UNCERTAIN, P11). oauth2-proxy v7 proxies upgrade requests, so it
  should pass authenticated; if 1.6.7 serves one and it fails, the tail
  degrades but nothing else breaks. Flag in the eval as a manual check.
- **N4 collision (documented, out of scope).** When N4 closes direct
  LAN access, Memex's and Prometheus's direct flows die, and
  `/metrics` via the edge sits behind the cookie gate with no skip.
  N4's plan must either add a skip/alternate scrape path or keep a
  pinhole. Carry via relay-finding onto N4.
- **Cookie name overlap with the dash proxy:** both instances use the
  default `_oauth2_proxy` cookie, but on different hosts with no
  `cookie_domains` set, so they cannot collide. Do not set
  `COOKIE_DOMAINS`.

## 10. Subtickets (ordered; single ticket, no separate plan files)

1. Vault side: OIDC client + key registration + `client_ids` append
   (`oidc.tf`), KV secrets (`secrets.tf`). Self-contained, applies
   cleanly before any job exists.
2. Proxy job: new jobspec + `nomad_job` wiring + firewall rule
   (`services.tf`). After apply the proxy runs but receives no traffic;
   verify via the Consul `/ping` check going green (direct probes to
   4181 are firewalled to HAProxy only).
3. Edge cutover: repoint `backend bifrost` to 4181
   (`haproxy.hcl:175-176`). Verify the live checks in §8.
4. Docs: `docs/haproxy_reverse_proxy.md`.
5. `just pre_commit` + adversarial review; hand the reviewer the
   skip-auth evidence and the §6.3 no-change assertion.

## 11. Open questions

- **Q1 — Scope: `openid` only, or `openid email`?** The `email` scope
  exists since G1 (`oidc.tf:85-90`, advertised at `:122-125`) and the
  operator entity carries the metadata, so requesting it works. L1
  requests `openid` only and maps `OIDC_EMAIL_CLAIM=sub`
  (`oauth2-proxy.hcl:69-70`). *Recommendation:* copy L1 (`openid` +
  `sub`). Flat access makes the email cosmetic, and fewer moving parts
  means fewer silent-drop surprises. Requesting `email` later is a
  two-line change.
- **Q2 — Proxy port.** 4181 is free (P8) and adjacent to L1's 4180.
  *Recommendation:* 4181.
- **Q3 — Other provider prefixes.** The operator chose exactly `/v1/*`
  and `/anthropic/*`. Bifrost also exposes other integration prefixes
  (e.g. `/openai/*`, `/genai/*`) upstream, and no in-repo consumer uses
  ANY prefix through the edge today (all direct, P3), so nothing breaks
  either way. *Recommendation:* keep the operator's exact list; widen
  only when a real edge client needs another prefix.

No `unmeasurable-requirement` forks: every §6 requirement is observable
from files in §7's surface or the live checks named in §8.

## Premises / assumptions

- **P1.** Bifrost serves UI, admin API, and inference all on one port,
  8080, host network, node 192.168.2.50. `Evidence:`
  `bifrost.hcl:11-15, :6-9, :40-41`; address at `:23` via
  `deployments/applications/services.tf:507`.
- **P2.** No Terraform or Consul health path goes through the edge, so
  the cookie gate cannot break them and no `/health` skip route is
  needed. `Evidence:` Consul check is registered on the service at
  address 192.168.2.50 (`bifrost.hcl:20-37`); the readiness poll and
  the bifrost provider both use the literal
  `http://192.168.2.50:8080` (`deployments/applications/services.tf:552-555,
  :561`; `deployments/applications/providers.tf:67`).
- **P3.** Every in-repo inference/scrape consumer bypasses the edge:
  `hermes.hcl:158` (loopback), `memex.hcl:168, :175, :178` (direct
  node), `prometheus.hcl:129-135` (direct node + basic auth). No file
  in the repo calls `https://bifrost.lab.orangecluster.nl` for
  inference (grep 2026-09-03: only `docs/haproxy_reverse_proxy.md`, a
  CLI test fixture, and the dash tile link).
- **P4.** `backend bifrost` is an unauthenticated pass-through and
  `backend dash` proves the edge-to-proxy shape on this same node:
  `haproxy.hcl:175-176, :178-179`.
- **P5.** The L1 proxy pattern is done and copyable: jobspec
  `oauth2-proxy.hcl` (traps `:10-23`, template `:58-76`, image v7.13.0
  `:95`), wiring `deployments/infrastructure/services.tf:465-489`,
  firewall `:334-341`. Its own header says R1/R4-class tickets copy it.
- **P6.** Vault consumer contract: `oidc.tf:92-107` (client-ids
  append), `:117-126` (provider `lab`), `:188-211` (confidential
  allow_all client + key registration), scope-request rule
  `docs/vault-human-auth.md:306-314`, branch-3 allow_all
  `:288-292`.
- **P7.** Secret shape and cookie trap:
  `deployments/infrastructure/secrets.tf:206-249`, base64url note
  `:227-230`.
- **P8.** Port 4181 is unused. `Probe:` `grep -rn '4181' deployments/ |
  wc -l` → `0` (2026-09-03, read-only).
- **P9 (external, verified 2026-09-03).** Bifrost OSS has no native
  OIDC (SSO is enterprise/"coming soon"); the admin API takes basic
  auth or a session bearer and rejects virtual keys; inference takes
  `x-bf-vk`/bearer/`x-api-key`. This is why a proxy at the edge is the
  design at all. `Source:`
  https://docs.getbifrost.ai/quickstart/gateway/setting-up-auth (built-in
  auth covers dashboard + `/api/*`),
  https://docs.getbifrost.ai/features/sso-with-google-github ("coming
  soon" stub), https://docs.getbifrost.ai/enterprise/advanced-governance
  (OIDC provisioning is enterprise), and
  `transports/bifrost-http/handlers/middlewares.go` in
  github.com/maximhq/bifrost (credential kinds per route class).
- **P10 (external, container-verify before relying).** oauth2-proxy
  v7.13 skip-auth is `OAUTH2_PROXY_SKIP_AUTH_ROUTES` (plural env,
  comma-separated, entries `regex` or `METHOD=regex`), and the regex is
  NOT implicitly anchored, so `^/v1/` and `^/anthropic/` are required
  to keep `/v1foo` gated. Per upstream docs; the exact matching
  behavior must be confirmed against a real v7.13.0 container the way
  L4 confirmed upstream path matching (`oauth2-proxy.hcl:46-57`).
- **P11 (UNCERTAIN).** Bifrost 1.6.7's dashboard may use a websocket
  for live log tailing, and oauth2-proxy v7 proxies upgrades. Cheap to
  check post-cutover; failure degrades only the log tail.
- **P12.** The repo gate is `just pre_commit` (`justfile:18-19`),
  running nomad-fmt, terraform-fmt, and `scripts/tf_validate.sh`
  (`.pre-commit-config.yaml:16-32`). `.loop/config.json` lists it as
  the sole gate and sets `require_eval`.
- **P13.** The `nomad-workloads` policy grants
  `secret/data/<namespace>/<job_id>/*`
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-5`),
  so the job name and its KV prefix must match:
  job `oauth2-proxy-bifrost` reads `default/oauth2-proxy-bifrost/*`.
- **P14.** B1, L1, F2, and G1 are all `done`, so admin auth, virtual
  keys, the proxy pattern, and the OIDC provider are the settled
  baseline and no `depends_on` gates are needed. `Probe:` stages read
  from `.loop/ledger.json` `entries.<slug>.stage` → `done` for all
  four (2026-09-03, read-only).
