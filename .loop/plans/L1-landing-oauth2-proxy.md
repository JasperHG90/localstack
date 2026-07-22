# L1 — oauth2-proxy forward-auth gate for the cluster landing page

## Title
Deploy oauth2-proxy as an OIDC client (against Vault's OIDC provider) that
gates the cluster landing page at the HAProxy edge, with a flat "any
authenticated user is allowed" policy and HTTPS-only cookies.

## Size / Effort
**Medium.** One new Nomad jobspec, one new `nomad_job` + secret in Terraform,
and one new HAProxy frontend ACL + backend. The effort driver is not line
count but the two cross-ticket seams: the exact Vault OIDC client
credential path (owned by F2) and the TLS edge bind (owned by F3). Neither
exists in the repo yet, so the ticket must parametrize those seams rather
than hardcode them.

## Triggered by
Home-lab auth epic. Human-facing services currently sit behind a single
shared HTTP basic-auth user (`openfang_users`) declared inline in
`deployments/infrastructure/services/haproxy.hcl:45-46` and applied to
phoenix/mlflow/bifrost backends (`haproxy.hcl:100,116,120`). The epic
replaces shared basic-auth with real SSO: Vault is the OIDC IdP (Zitadel
dropped), and oauth2-proxy is the per-edge gate. L1 lands that gate for the
landing page first and establishes the reusable pattern that R1 (MLflow)
and R4 (Phoenix) will copy.

## Context (today's state)
- Edge is a single HAProxy job pinned to host `firebat`, binding **cleartext
  `*:80` only** (`haproxy.hcl:11-19`, `48-49`). There is no TLS bind today;
  F3 adds it.
- Routing is a flat list of `hdr(host)` ACLs plus `use_backend` in one
  frontend (`haproxy.hcl:48-75`) with static `server ip:port` backends
  (`haproxy.hcl:84-121`). Backends are static, not Consul-discovered.
- Existing auth is HTTP basic-auth: a `userlist` (`haproxy.hcl:45-46`) fed by
  a Terraform `random_password` (`secrets.tf:31-44`,
  `services.tf:308-316`), enforced per-backend via
  `http-request auth unless { http_auth(openfang_users) }`
  (`haproxy.hcl:100,116,120`).
- **No landing-page service and no `dash.localstack` ACL/backend exist**
  today (`grep dash` in `haproxy.hcl` returns nothing; the only `dash`
  matches in the tree are Grafana *dashboard* files).
- **No Vault OIDC provider or `vault_identity_oidc_client` resource exists**
  yet (`grep -rn 'vault_identity_oidc\|oidc_provider\|issuer' deployments/**/*.tf`
  returns nothing). That is F2's deliverable.
- Vault-templated-secret pattern to copy: Grafana declares `vault {}`
  (`grafana.hcl:29`) and injects a secret through
  `template { ... env = true }` reading
  `{{ with secret "<path>" }}{{ .Data.data.<key> }}{{ end }}`
  (`grafana.hcl:77-84`). Secret paths are passed in from Terraform via
  `templatefile(...)` vars (`services.tf:333-355`), and the secret itself is
  a `random_password` + `vault_kv_secret_v2` pair (`secrets.tf:46-66`).
- Nomad-job wiring pattern to copy: `resource "nomad_job" "<name>"` with
  `jobspec = templatefile("${path.module}/services/<name>.hcl", { ... })`
  (`services.tf:301-316` for HAProxy; `services.tf:333-355` for Grafana).
- Providers available: `nomad` and `vault` only (`providers.tf:1-28`); no
  Consul provider is enabled.

## Non-goals / out of scope
- **No per-user RBAC or group/role mapping.** Access is FLAT: anyone who
  completes Vault login is allowed through. Fine-grained authz is IdP
  territory and is explicitly not wanted.
- **Not F2.** This ticket does not create the Vault OIDC provider, the
  `vault_identity_oidc_client` for oauth2-proxy, the issuer, or the human
  user/identity setup. It consumes them.
- **Not F3.** This ticket does not add the TLS `bind ... ssl` at HAProxy or
  provision Vault PKI certs. It assumes the edge serves HTTPS and sets
  cookie flags accordingly.
- **Not R1/R4.** Do not wire MLflow or Phoenix through oauth2-proxy here.
  L1 only establishes the reusable pattern and documents it.
- Do not migrate or remove the existing `openfang` basic-auth on
  phoenix/mlflow/bifrost backends. Leave them untouched.
- Do not build the landing-page content/app itself if the operator decides
  it is a separate ticket (see Open Questions Q1).

## Requirements & restrictions
1. oauth2-proxy runs as a Nomad `service` job under
   `deployments/infrastructure/services/`, driver `podman`, using an
   **arm64-compatible image** (cluster nodes are Orange Pi / ARM boards per
   `CLAUDE.md` "Project Overview"). Pin an explicit image tag, matching the
   pinned-tag convention (e.g. `grafana.hcl:48`, `nats.hcl:69`).
2. Client credentials (`client_id`, `client_secret`), the cookie secret, and
   the Vault issuer/discovery URL are injected via a Vault-templated
   `template { env = true }` block reading `secret/data/<ns>/<job>/<entry>`,
   never hardcoded (`CLAUDE.md` Secrets convention; pattern
   `grafana.hcl:77-84`). Requires a `vault {}` stanza (pattern
   `grafana.hcl:29`).
3. The cookie secret is generated in Terraform as a `random_password` and
   written to Vault KV2, mirroring `secrets.tf:46-66`. oauth2-proxy requires
   the cookie secret to be exactly 16, 24, or 32 bytes — size it so the
   stored value decodes to one of those lengths (see Open Questions Q3).
4. Redirect URL is `https://dash.localstack/oauth2/callback`; cookies must be
   set `Secure` (`--cookie-secure=true`) so they never traverse cleartext.
   This is why the ticket depends on F3.
5. Flat access: configure the "any successful login is authorized" policy
   (in oauth2-proxy this is the default once no `--allowed-*` restriction is
   set; do not add email-domain/group allowlists). State this explicitly in
   the jobspec via a comment so R1/R4 copyists do not add restrictions.
6. Wire the gate into HAProxy for the `dash.localstack` host: add the ACL +
   `use_backend` in the frontend (`haproxy.hcl:48-75`) and the backend
   definition (alongside `haproxy.hcl:84-121`). See Open Questions Q2 for
   the forward-auth-vs-reverse-proxy fork; the recommendation is
   reverse-proxy mode so HAProxy routes `dash.localstack` to oauth2-proxy as
   an ordinary backend.
7. Terraform must add a `resource "nomad_job" "oauth2_proxy"` using
   `templatefile(...)` (pattern `services.tf:301-316`) and pass the Vault
   secret path(s) as template vars (pattern `services.tf:333-355`).
8. Reusability: document (in a comment header in the new jobspec, and/or the
   HAProxy backend comment) that the same job/pattern fronts MLflow (R1) and
   Phoenix (R4). Keep host/redirect/issuer values as template vars so the
   pattern is copyable without editing the job body. Respect `CLAUDE.md`
   Simplicity/Surgical rules: no speculative multi-app config now.
9. Match existing HCL style; the gate reformats via `nomad fmt` (see below).

## Code surface
- `deployments/infrastructure/services/oauth2-proxy.hcl` **(new)** — the
  Nomad job: `podman` task, arm64 image, `vault {}` stanza, a
  `template { env = true }` block for `OAUTH2_PROXY_*` env (client id/secret,
  cookie secret, OIDC issuer, redirect URL), a `service` + health `check`
  (pattern `nats.hcl:50-66`, `grafana.hcl:31-45`), `network` port, and a
  `resources` block. Header comment noting R1/R4 reuse.
- `deployments/infrastructure/services.tf:308-316` — add a new
  `resource "nomad_job" "oauth2_proxy"` block near the HAProxy job, using
  `templatefile` with the Vault secret path var(s); pattern to copy is the
  Grafana block at `services.tf:333-355`.
- `deployments/infrastructure/secrets.tf:46-66` — add a `random_password`
  (cookie secret) + `vault_kv_secret_v2` (path
  `default/oauth2-proxy/<entry>`) pair, mirroring the Grafana admin block.
  If F2 does not already store the OIDC client secret in Vault, this file is
  also where a placeholder/reference for it is surfaced (see Q4).
- `deployments/infrastructure/services/haproxy.hcl:48-75` — add
  `acl is_dash hdr(host) -i dash.localstack` and
  `use_backend dash if is_dash` in the `http_in` frontend.
- `deployments/infrastructure/services/haproxy.hcl:84-121` — add a `backend
  dash` pointing at the oauth2-proxy service address:port (static
  `server` line, matching existing backend style).
- `deployments/infrastructure/variables.tf:1-21` — if the OIDC
  issuer/provider name or oauth2-proxy host is operator-supplied, add a
  `variable` here and thread it through `prod.tfvars`
  (`vars/prod.tfvars:1-4`).

## Tests & validation gates

### Repo gate (blessed invocation): `just pre_commit`
Runs `pre-commit run --all-files` (root `justfile` `pre_commit` recipe). The
config is now **Terraform-aware**, so this single command is the full
pre-apply gate for both the HCL jobspec and the `.tf` changes
(`.pre-commit-config.yaml`):
- `nomad-fmt` (`nomad fmt -recursive`, local hook, `types: [hcl]`) on every
  `*.hcl`. New/edited jobspec HCL must be `nomad fmt`-clean; run
  `just format` first.
- `terraform-fmt` (`terraform fmt -check -recursive`, local hook,
  `types: [terraform]`) on every `*.tf`. Edits to `services.tf`,
  `secrets.tf`, and `variables.tf` must be `terraform fmt`-clean.
- `terraform-validate` (`scripts/tf_validate.sh`, local hook,
  `types: [terraform]`) — validates every Terraform root offline
  (`init -backend=false` then `terraform validate`, no remote state, no
  credentials). The new `nomad_job`, `random_password`, and
  `vault_kv_secret_v2` resources must pass `terraform validate` here; this is
  part of the gate, not a separate manual step.
- `check-json` / `check-yaml --unsafe` / `end-of-file-fixer` /
  `detect-private-key` on touched files. The generated cookie/client secrets
  live in Vault, never in-repo, so `detect-private-key` must stay green.
- `.pre-commit-config.yaml` sets `exclude: '^\.(claude|loop)/'`, so this
  ticket file and the `.loop/` tree are not linted.

There is no unit-test harness for Nomad/Terraform jobspecs in this repo (no
pytest, no CI workflow; the Python testing rule in
`.claude/rules/python-testing.md` does not apply to HCL). `terraform
validate` via the gate is the static check; behavioral verification is the
live evals below.

### Evals (live) — runnable acceptance
The cluster is reachable from this environment: `VAULT_ADDR`, `VAULT_TOKEN`,
`NOMAD_ADDR`, `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are set, so the acceptance
checks below are runnable, not just documentation.

**Hard dependencies.** The close-out evals require F2 and F3 merged and
applied:
- **F2 (OIDC client):** without the `vault_identity_oidc_client` and the
  provider issuer, oauth2-proxy has no client to authenticate and no
  authorize endpoint to redirect to — startup or login fails.
- **F3 (TLS bind):** with `--cookie-secure=true` over a cleartext `*:80`
  edge, the browser drops the session cookie and re-loops to login. Do not
  run the completed-flow eval before F3 is in.

**Pre-apply (runs in the loop, no cluster mutation):**
1. `just pre_commit` — green (includes `terraform fmt -check` and
   `terraform validate` on the new resources, per the gate above).

**Close-out (operator/live, after F2 + F3 are applied). Each check lists the
command and the expected result:**

1. **oauth2-proxy allocation is healthy.**
   - Command: `nomad job status oauth2-proxy`
   - Expect: `Status = running`, the latest deployment `Successful`, and a
     `running`/`healthy` allocation (0 failed).

2. **Unauthenticated request to the protected route redirects to Vault
   OIDC.**
   - Command: `curl -sI https://dash.localstack/`
   - Expect: `HTTP/2 302` with a `Location:` header pointing at the Vault
     OIDC authorize endpoint, i.e. under
     `$VAULT_ADDR/v1/identity/oidc/provider/<provider-name>/authorize?...`
     (or the `$VAULT_ADDR/ui/vault/identity/oidc/...` provider authorize URL).
     The host and path must match F2's issuer (Risk assessment failure mode
     3).

3. **The `/oauth2/callback` route exists (is served by oauth2-proxy).**
   - Command: `curl -sI https://dash.localstack/oauth2/callback`
   - Expect: **not** `404`. oauth2-proxy handles the route (a `302`/`400`
     from the proxy is fine); a `404` means the callback path was never
     wired.

4. **Session cookie is `Secure` + `HttpOnly` (requires F3 TLS).**
   - Command: `curl -sI https://dash.localstack/ | grep -i set-cookie`
   - Expect: the `_oauth2_proxy` cookie in `Set-Cookie` carries both
     `Secure` and `HttpOnly` attributes, confirming cookies never traverse
     cleartext.

5. **A completed auth-code flow yields an allowed request.**
   - Command: complete the Vault login for `https://dash.localstack/` in a
     browser (or a scripted authorization-code flow), then re-request
     `curl -sI https://dash.localstack/` with the session cookie.
   - Expect: `HTTP/2 200` reaching the landing-page upstream, confirming the
     flat "any authenticated user allowed" policy lets the session through.

The loop's definition of done is: `just pre_commit` green (which now includes
`terraform validate`), and the five live evals above recorded in the
ticket/PR description — pre-apply eval run in the loop, close-out evals run by
the operator against applied F2 + F3.

Eval marker (five-column acceptance table, `loopctl eval`-validated): see
`.loop/evals/L1-landing-oauth2-proxy.md`.

## Risk assessment
- **Blast radius:** additive. New job, new secret, new HAProxy ACL/backend.
  The existing frontend ACLs and basic-auth backends
  (`haproxy.hcl:48-121`) are untouched, so current services keep working.
  The one shared-blast surface is `haproxy.hcl` itself: a malformed edit to
  the single `http_in` frontend config breaks *all* routing, since every
  host shares that one frontend. Keep the edit purely additive and
  `nomad fmt`-clean.
- **Reversibility:** high. Removing the `nomad_job`, the ACL/backend lines,
  and the secret reverts cleanly; no state migration, no data.
- **Likeliest failure modes:**
  1. **Redirect loop / cleartext cookie** if F3's TLS bind is not present:
     `--cookie-secure=true` over `*:80` means the browser drops the cookie
     and re-loops to login. This is the dependency landmine — do not merge
     ahead of F3, or gate cookie-secure behind the TLS bind.
  2. **Wrong Vault client path** (F2 seam): if the
     `vault_identity_oidc_client` credential path/keys differ from what the
     template reads, the job boots but every login 500s. Parametrize the
     path; confirm against F2 before apply.
  3. **Issuer/discovery URL mismatch:** oauth2-proxy validates the OIDC
     discovery document; a wrong issuer host (`vault.localstack` vs internal
     IP) fails startup. Must match F2's provider issuer exactly.
  4. **arm64 image tag** that is amd64-only fails to pull on the Orange Pi
     nodes — verify the tag is multi-arch/arm64.

## Subtickets (ordered, dependency-aware)
1. **Provision the cookie secret in Terraform.** Add `random_password` +
   `vault_kv_secret_v2` at `default/oauth2-proxy/<entry>` (mirror
   `secrets.tf:46-66`). Verify: `terraform validate`.
2. **Write `oauth2-proxy.hcl`.** Nomad job: arm64 image, `vault {}`,
   `template { env = true }` for the `OAUTH2_PROXY_*` env, service+check,
   network port, resources. Flat-access comment + R1/R4 reuse header.
   Verify: `just format` then `just pre_commit` green on the file.
3. **Wire the `nomad_job` in `services.tf`.** `templatefile` block passing
   the Vault path var(s) (pattern `services.tf:333-355`). Verify:
   `terraform validate`.
4. **Add the HAProxy `dash` route.** ACL + `use_backend`
   (`haproxy.hcl:48-75`) and `backend dash` (`haproxy.hcl:84-121`) pointing
   at oauth2-proxy. Verify: `just pre_commit` green (nomad fmt).
5. **Record acceptance checks** in the PR/ticket description for the operator
   to run post-F2/F3 (the three success-criteria curls). No code change.

## Open questions (forks for the operator to settle first)
- **Q1 — Does L1 include the landing-page service itself, or only the auth
  gate?** No `dash.localstack` backend or landing app exists today. The
  ticket as scoped wires oauth2-proxy as the `dash` backend and treats the
  landing page content as either (a) served by oauth2-proxy's upstream, or
  (b) a separate ticket. *Recommendation:* keep L1 to the auth gate plus the
  HAProxy route, and point the oauth2-proxy upstream at a minimal
  placeholder (or the existing HAProxy stats/a static page) until a
  dedicated landing-page ticket lands. Confirm which.
- **Q2 — Forward-auth vs reverse-proxy mode.** HAProxy has no native
  nginx-style `auth_request`; enforcing forward-auth needs SPOE/Lua, which is
  heavier than anything in the current config. The lighter path is running
  oauth2-proxy in reverse-proxy mode (`--upstream=<landing>`) and making it
  the `dash` backend so HAProxy just routes to it. *Recommendation:*
  reverse-proxy mode. Confirm before implementing, because it decides the
  jobspec's `--upstream`/`--http-address` flags and whether the landing
  backend is referenced by HAProxy or by oauth2-proxy.
- **Q3 — Cookie secret length/encoding.** oauth2-proxy requires 16/24/32
  bytes. A `random_password { length = 32, special = false }` yields 32 ASCII
  chars = 32 bytes, which is valid directly. *Recommendation:* `length = 32,
  special = false` and pass raw (no base64) to `OAUTH2_PROXY_COOKIE_SECRET`.
  Confirm the operator is happy with raw-32 vs a base64url-encoded 32-byte
  value.
- **Q4 — Where do the F2 OIDC client credentials live in Vault?** The epic
  says client_id/secret come from F2's `vault_identity_oidc_client`, but F2
  is not merged and no path exists in-repo. The template needs an exact
  `secret/data/<ns>/oauth2-proxy/<entry>` (or a direct read of the identity
  client) path and key names. *Recommendation:* agree with F2 that it writes
  the client_id/secret to `secret/data/default/oauth2-proxy/oidc` with keys
  `client_id`/`client_secret`, and make L1 read that path. Block apply (not
  the loop's HCL work) until F2 confirms.
- **Q5 — OIDC issuer/discovery URL.** Needs the exact issuer, likely
  `https://vault.localstack/v1/identity/oidc/provider/<provider-name>`, where
  `<provider-name>` is F2's choice. *Recommendation:* thread it as a
  Terraform variable (`variables.tf`) defaulted to the expected value, so it
  is set once F2 names the provider.
- **Q6 — Which host and static port for oauth2-proxy?** Every job pins
  `attr.unique.hostname`. *Recommendation:* colocate on `firebat` (the
  HAProxy edge host, `haproxy.hcl:6-9`) with a static port, so the HAProxy
  `backend dash` server line is a localhost/`firebat` address. Confirm host
  choice and free port.
- **Q7 — Cookie-secure vs F3 ordering.** `--cookie-secure=true` only works
  once F3's TLS bind exists. *Recommendation:* implement with
  cookie-secure=true and hard-block merge/apply until F3 is in, rather than
  shipping a cleartext-cookie interim. Confirm the operator wants the hard
  dependency (vs a temporary cookie-secure=false, which is discouraged).
