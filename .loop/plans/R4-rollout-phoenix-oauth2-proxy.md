---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider", "T3-tls-edge-cutover-lab-domain", "A1-audit-plan-premise-sweep"]
priority = 5
summary = "Turn on Phoenix's own authentication and point its generic OIDC client at Vault, instead of fronting it with oauth2-proxy. Phoenix speaks OIDC natively and authenticates OTLP ingest with a bearer key on the same port, so the port-6006 split, the extra proxy job, and the L1 dependency all disappear. Enabling auth blocks ingest until the sender presents a key, so the memex job gains an OTLP auth header in the same change."
tags = ["phoenix", "oidc", "vault", "terraform", "otlp"]
---

# Ticket: R4-rollout-phoenix-oauth2-proxy

> **Rewritten 2026-07-26.** The previous plan's central premise, "Phoenix has
> **no native OIDC**, so the UI is fronted by oauth2-proxy" (old §3), is false.
> Phoenix supports a generic OIDC provider and authenticates programmatic
> access with bearer keys. The oauth2-proxy design, the port-6006 split, and
> the L1 dependency are all consequences of that premise and are removed. The
> operator's 2026-07-23 fork resolutions are carried forward or marked
> superseded in §11. The cancelled content remains in git history.
>
> **The slug still says `oauth2-proxy` and now misdescribes the ticket.** See
> §12.
>
> **Relayed from `G1-grafana-native-oidc-login` (done, commit `1a57356`,
> 2026-09-03). Two of this plan's premises are now false, and part of §7 is
> already built.** G1 hit the identical email-claim wall and resolved it at the
> Vault end, so:
>
> - **The `email` scope EXISTS.** `oidc.tf` now declares
>   `vault_identity_oidc_scope.email` with the unquoted template
>   `{"email":{{identity.entity.metadata.email}}}`, and the `lab` provider's
>   `scopes_supported` is `[groups, email]`. **Consume it. Do not declare a
>   second one** — G1 created it as shared infrastructure precisely so R4 would
>   not. Declaring another is a duplicate-resource error on first plan.
> - **The operator entity DOES carry an email.**
>   `vault_identity_entity.operator` has an `email` metadata key, sourced from
>   the new `vault_operator_email` variable. Any NEW human entity needs the
>   same key or its owner cannot complete an OIDC login.
> - Consequently the first two bullets of §7's Vault-side work are **done**,
>   and §4's "The provider advertises exactly one scope, and it is not `email`"
>   is superseded. The rest of §7 stands.
> - **This plan's existing `unresolved-design-fork` blocker is stale.** Its
>   stated reason is that Vault emits no email and drops the scope silently, so
>   the callback dies after a successful login. G1 fixed exactly that. Re-run
>   the plan reviewer before dispatching R4 rather than simply unblocking it:
>   these premise edits were relayed, not re-reviewed.
> - **`depends_on` does NOT list G1.** Left alone deliberately, since adding a
>   dependency edge is the operator's call. G1 is `done`, so the edge would
>   gate nothing today; it would only record the lineage.

## 1. Title

Enable Phoenix's built-in authentication and point its generic OIDC client at
Vault's OIDC provider, so a browser must complete a Vault login to reach the
Phoenix console, and authenticate OTLP trace ingest with a bearer key rather
than leaving it open. No proxy in front of Phoenix.

## 2. Size / Effort

**Small.** Configuration only on both sides: a handful of `PHOENIX_*` env
settings in an existing Vault-templated block, one OIDC client in Terraform,
**two** secrets in KV2 (`PHOENIX_SECRET` and `PHOENIX_ADMIN_SECRET` — the OIDC
client secret is not one of them; on the recommended public-client route it
does not exist), one added env line on the `memex` job, and **one deleted
HAProxy line** (`haproxy.hcl:143`, per requirement 3 and §10 step 8). No new
job, no proxy, no application code.

Turning auth on **blocks all trace ingest until the sender presents a key**, so
the `memex` side is not optional. It is a one-line job change: `memex` already
supports OTLP exporter headers — see P15, verified against the deployed
container on 2026-08-04, with §10 step 1 re-checking it since the image tag
can move. The remaining effort
is the Phoenix callback path, which is version-dependent against a `:latest`
image, and the sequencing so ingest is never dark between applies (§9).

## 3. Triggered by

Home-lab auth epic, per-service rollout step for Phoenix. CONFIRMED: Vault is
the OIDC provider for humans (Zitadel dropped); Nomad Workload-Identity JWTs
are machine identity.

The rewrite itself was triggered by the operator on 2026-07-26, who noticed
that Phoenix documents native authentication:
https://arize.com/docs/phoenix/self-hosting/features/authentication

This is the same correction G1 applies to Grafana, and the same failure pattern
A1 was created to sweep for: a plan premise that was never true, surrounded by
`path:line` anchors that all still resolve.

## 4. Context (re-anchored 2026-08-04)

Verified 2026-07-26 against the repo and the running cluster; every anchor
re-checked 2026-08-04 after the plan-validator found three stale ones.

- **Phoenix runs under `applications/`, not `infrastructure/`.** The job is
  `deployments/applications/services/phoenix.hcl`, rendered by
  `deployments/applications/services.tf:125-134` with `phoenix_host =
  "192.168.2.29"`. It runs `network_mode = "host"` (`phoenix.hcl:54`) on
  `orangepi4a` (the constraint is `phoenix.hcl:6-9`) and is live: `curl
  http://192.168.2.29:6006/healthz` returns `200`.
- **The job has exactly one env template today** (`phoenix.hcl:59-66`),
  injecting `PHOENIX_SQL_DATABASE_URL` from Vault KV2. It already carries a
  `vault {}` stanza (`phoenix.hcl:57`). This is the block the new settings
  extend; no new mechanism is required. Phoenix is already Postgres-backed,
  which is where it stores its user table.
- **Two static ports** (`phoenix.hcl:12-17`): `6006` serves the web UI **and**
  the HTTP OTLP collector (`/v1/traces`); `4317` serves gRPC OTLP.
- **`memex` is the only in-repo trace sender.**
  `deployments/applications/services/memex.hcl:168-169` sets
  `MEMEX_SERVER__TRACING__ENABLED=true` and
  `MEMEX_SERVER__TRACING__ENDPOINT=http://${phoenix_host}:6006/v1/traces`. The
  job sets no header today.

  **`memex` supports an OTLP exporter header, but this repo can no longer
  show you where.** The 2026-07-26 rewrite cited a vendored checkout under
  `apm_modules/JasperHG90/memex` (`TracingConfig.headers`, and its pass-through
  to `OTLPSpanExporter`). That directory is gitignored and is **not present in
  this checkout or in a ticket worktree**, so those citations resolve to
  nothing and have been removed rather than left as anchors an implementer
  cannot open. The capability itself is **verified** (P15, 2026-08-04): the
  field exists in the running container. §10 step 1 re-checks it directly
  against the container rather than a path, because the image tag can move.

  Two things the implementer must confirm rather than assume:
  - The env spelling follows the existing `__` nesting convention, so
    `MEMEX_SERVER__TRACING__HEADERS`, supplied as a JSON object because the
    field is a `dict`. **Confirm the exact form pydantic-settings accepts in
    the deployed build before applying**, since a silently unparsed value
    means traces stop.
  - The deployed image is `ghcr.io/jasperhg90/memex-jetson`. Confirm that build
    carries the field. If it does not, upgrading it is a dependency of this
    ticket (§5), not work done here.
- **Phoenix's image is the mutable tag `docker.io/arizephoenix/phoenix:latest`
  (`phoenix.hcl:53`).** Nobody can tell from the repo which Phoenix version is
  running, and OIDC role mapping and auth env vars vary by version. It is also
  the only unpinned image in the applications layer, which sits at odds with
  the T4 digest-pinning commit. Pinning it is out of scope here (§5) but is a
  precondition the implementer should raise, not silently absorb.
- **HAProxy** (`deployments/infrastructure/services/haproxy.hcl`) routes
  Phoenix by host ACL (`:103`, `:114`) to `backend phoenix` (`:142-144`),
  which applies shared basic auth at `:143`
  (`http-request auth unless { http_auth(openfang_users) }`) against the
  `openfang_users` userlist (`:88`). **Only two backends still carry that
  line: phoenix (`:143`) and mlflow (`:153`).** Bifrost's was deleted by B1 in
  commit `ac3267b` on 2026-07-29, and `backend bifrost` (`:156-157`) is now a
  bare `server` line. Post-T3 the edge serves TLS on `*:443` (`:95-96`) and
  `*:80` is a 301 (`:91-93`); the hostname is `phoenix.lab.orangecluster.nl`.
- **Vault's OIDC provider exists and F2 is `done`.** The issuer is
  `vault_identity_oidc_provider.lab` (`deployments/infrastructure/oidc.tf:95-101`),
  with `https_enabled = true`, so the discovery URL is
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration`.
  That matters: Phoenix rejects a non-HTTPS `OIDC_CONFIG_URL` for anything but
  localhost, and this issuer satisfies it. Consumers must point at `lab`, never
  Vault's built-in `default` provider, whose `allowed_client_ids` is `["*"]`
  and whose issuer is a raw-IP `http://` URL.
- **The provider advertises exactly one scope, and it is not `email`.**
  `oidc.tf:100` is `scopes_supported = [vault_identity_oidc_scope.groups.name]`,
  and `oidc.tf:55-70` defines that sole `groups` scope. There is no `email`
  scope and no entity carries an email: `vault_identity_entity.operator`
  (`deployments/infrastructure/auth_userpass.tf:38-44`) has `managed_by` and
  `kind` metadata only. **This is the defect that sinks the naive version of
  this ticket** — see the next section.
- **F2's consumer contract, which this ticket must follow.** `oidc.tf:28-40`
  spells it out: the shared `lab` key deliberately does not set
  `allowed_client_ids` inline, so a consumer registers itself with a standalone
  `vault_identity_oidc_key_allowed_client_id`; the provider has no such
  standalone resource, so a consumer appends its client id to
  `local.oidc_provider_client_ids` (`oidc.tf:80-84`). F2 names R4 as one of
  four consumers wanting flat access, for which the contract is
  `assignments = ["allow_all"]` (`oidc.tf:22-23`). `memex_oidc.tf` is the
  worked example of a consumer that followed all of it.

### The email claim, and why the obvious wiring fails

Phoenix always requests `openid email profile` and **hard-requires an `email`
claim** to identify the user; without one the callback fails with
`missing_email_scope` after an otherwise successful Vault login.

Vault does not error on a scope it does not support. It **silently drops it**.
This repo's own documentation says so:
`docs/vault-human-auth.md:447-449` — "`scopes` MUST include `groups`. Vault
ignores an unsupported scope rather than [erroring], [leaving a] valid token
carrying no `groups` claim, which then matches no grant rule." The same
mechanism applies to `email`, in the other direction: Phoenix asks for it,
Vault drops it, the token is signed and valid and has no email, and login dies
at the callback with a generic error.

So a Phoenix client plus its env settings is **not** enough on its own. Three
more things are needed, and this ticket owns all three because F2 is `done`
and shipped only the `groups` scope:

1. An email on the identity. Add `email` to the metadata map of
   `vault_identity_entity.operator` (`auth_userpass.tf:38-44`), sourced from a
   new variable rather than a literal.
2. A `vault_identity_oidc_scope` named `email` whose template emits the claim.
   **Do not quote the placeholder.** The literal is:

       {"email":{{identity.entity.metadata.email}}}

   This is the **same** rule as the `groups` scope beside it, not the opposite.
   `oidc.tf:59-69` states the general rule accurately — "Vault's identity
   templating emits fully-formed JSON per substitution" — and the list is only
   its example. A metadata lookup is already quoted when it is substituted:
   `jsonTemplateHandler` in `sdk/helper/identitytpl/templating.go` returns
   `strconv.Quote(t[keys[0]])` for a `map[string]string`. Adding quotes of
   your own yields `{"email":""a@b.com""}`.
   **The wrong version fails loudly, at `terraform apply`, not silently.**
   Scope creation validates the template against a zero-value entity, so the
   quoted form renders `{"email":""""}` and Vault rejects it with a template
   JSON parse error. Trust that error rather than "fixing" it by adding
   quotes.
3. That scope added to `oidc.tf:100`'s `scopes_supported`. **This is a second
   line of `oidc.tf` a consumer edits**, which F2's contract comment
   (`oidc.tf:39-40`, "That single marked line is the whole contract") does not
   anticipate. Record it as a finding for F2's documentation (§12).

`PHOENIX_OAUTH2_VAULT_EMAIL_ATTRIBUTE_PATH` is the fallback lever if the claim
lands under a different key than Phoenix expects. Confirm it exists on the
deployed version before relying on it.

### What Phoenix actually supports

From the authentication doc, fetched 2026-07-26:

- `PHOENIX_ENABLE_AUTH=True` plus `PHOENIX_SECRET` (a long JWT-signing string)
  turns authentication on.
- **Generic OIDC**: `PHOENIX_OAUTH2_<IDP>_CLIENT_ID`,
  `PHOENIX_OAUTH2_<IDP>_CLIENT_SECRET`, `PHOENIX_OAUTH2_<IDP>_OIDC_CONFIG_URL`.
  The doc's wording is "any IDPs that support OpenID Connect and a well-known
  configuration endpoint", which Vault's OIDC provider publishes.
- **Programmatic access uses bearer keys**: `Authorization: Bearer <key>`. The
  doc notes the header field must be **lowercased** for gRPC compatibility.
- **`PHOENIX_ADMIN_SECRET`**: a bearer token settable by env var that
  authenticates as the first system user, usable instead of a UI-minted API
  key. Minimum 32 characters, at least one digit and one lowercase letter, must
  differ from `PHOENIX_SECRET`. **This is what makes the ticket automatable**:
  system API keys are otherwise UI-only, which no Terraform run can do.
- Enabling auth "will stop collecting traces and block all API access until API
  keys are created". There is no unauthenticated-ingest escape hatch.

## 5. Non-goals / out of scope

- **Deploying oauth2-proxy for Phoenix.** Phoenix has a native OIDC client; a
  proxy would be a second, redundant auth layer. This is the reversal.
- Creating the Vault OIDC issuer, key, or scopes. That is F2.
- Changing `memex`'s application code. The ingest credential is configuration
  (§4); if the deployed image turns out to lack `TracingConfig.headers`,
  upgrading it is a dependency of this ticket, not work done here.
- Authenticating `memex`'s own HTTP surface. `memex.hcl:138-140` already gates
  it with API keys, and its edge auth is a separate gap (§12).
- Pinning `phoenix:latest` to a digest. Real, and it should be its own ticket
  (§12), but it is not this ticket's subject.
- Removing HAProxy's shared basic auth from MLflow. `haproxy.hcl:153` is left
  alone; only the Phoenix line at `:143` is touched. Bifrost is not mentioned
  because it no longer has one (B1, `ac3267b`).
- Changing where Phoenix runs, its ports, or its Postgres backing.
- Role or group mapping beyond flat access. See Q3.
- LDAP, and Phoenix's built-in OAuth2 authorization server for MCP/CLI clients.

## 6. Requirements & restrictions

Must achieve:

1. Browsing `https://phoenix.lab.orangecluster.nl` requires a completed Vault
   OIDC login. An unauthenticated browser is not served the console.
2. **OTLP trace ingest keeps working.** `memex` traces continue to arrive after
   auth is enabled. This is the load-bearing guardrail, same as in the previous
   plan, for a different reason: the risk is now an unauthenticated sender
   rather than an intercepting proxy.
3. The HAProxy shared basic-auth line on the Phoenix backend
   (`haproxy.hcl:143`) is **removed**, not stacked on top of Phoenix's own
   login. Leave MLflow's line (`:153`) alone. Bifrost has none to leave.
4. `PHOENIX_SECRET` and `PHOENIX_ADMIN_SECRET` are distinct values, both
   generated by Terraform `random_password` and stored in Vault KV2, never
   committed. **Both** must satisfy the same complexity rule (>=32 chars, >=1
   digit, >=1 lowercase) — Phoenix applies it to `PHOENIX_SECRET` too, not
   just the admin secret — and `random_password` does not guarantee it by
   default. Set `min_lower` and `min_numeric` explicitly on **both**
   resources, or a later rotation can generate a value Phoenix refuses at
   boot.
5. A way in that does not depend on Vault survives, or its absence is an
   explicit operator decision. See Q2.
6. **The ID token Vault issues to Phoenix carries an `email` claim.** This is
   a hard requirement, not a nicety: Phoenix fails the callback without it, and
   Vault will not tell you the scope was dropped. Satisfying it means all three
   of the email scope, its presence in the provider's `scopes_supported`, and
   an entity that carries the value (§4). Verify by decoding the issued token,
   not by the login appearing to succeed.
7. Phoenix's redirect URI matches what Phoenix actually sends. The route is
   `/oauth2/<idp_name>/tokens`, so with `<IDP>` = `vault` the registered URI is
   `https://phoenix.lab.orangecluster.nl/oauth2/vault/tokens`. A mismatch
   presents as an opaque `invalid redirect_uri` from Vault.

Restrictions the repo enforces:

- Secrets live in Vault KV2 and reach the job through `template { env = true }`
  (`CLAUDE.md` Key Conventions; the shape is at `phoenix.hcl:59-66` and
  `deployments/infrastructure/secrets.tf`). `detect-private-key` runs in
  pre-commit.
- The OIDC client is declared in Terraform beside F2's other clients, never
  created by hand in Vault.
- Terraform provider pins at `providers.tf` are authoritative. Do not bump.
- Surgical changes only (`CLAUDE.md` §3): the Phoenix backend line, the Phoenix
  job's env template, and the new Terraform resources. Nothing adjacent.
- Adversarial review before done (`.claude/rules/adversarial-reviews.md`). Hand
  the reviewer the ingest-survival evidence specifically.

## 7. Code surface

- **`deployments/applications/services/phoenix.hcl:59-66`** — extend the
  existing env template with `PHOENIX_ENABLE_AUTH`, `PHOENIX_SECRET`,
  `PHOENIX_ADMIN_SECRET`, `PHOENIX_USE_SECURE_COOKIES` (post-T3 the edge is
  HTTPS), and the OIDC client settings. **On the recommended public-client
  route those are four, and `CLIENT_SECRET` is not one of them:**

      PHOENIX_OAUTH2_VAULT_CLIENT_ID
      PHOENIX_OAUTH2_VAULT_OIDC_CONFIG_URL
      PHOENIX_OAUTH2_VAULT_TOKEN_ENDPOINT_AUTH_METHOD=none
      PHOENIX_OAUTH2_VAULT_USE_PKCE=true

  `USE_PKCE` must be exactly `true` or `false`; Phoenix raises on `1`.
  `OIDC_CONFIG_URL` stays required on the public route — there is no
  public-client exemption.

  Getting this wrong is a hard boot failure rather than a subtle one: Phoenix
  makes `CLIENT_SECRET` **required** whenever `TOKEN_ENDPOINT_AUTH_METHOD` is
  unset, and Vault issues no secret for a public client, so omitting the
  auth-method setting sends the implementer hunting for a secret that does not
  exist. A confidential client instead needs `CLIENT_ID`, `CLIENT_SECRET` and
  `OIDC_CONFIG_URL`. Values come from Vault, not literals.
- **`deployments/applications/services.tf:125-134`** — thread the new Vault
  secret paths into the Phoenix `templatefile(...)` var map, following the
  `phoenix_secret` var already there.
- **`deployments/infrastructure/oidc.tf:95-101`** — add a
  `vault_identity_oidc_client` for Phoenix with redirect URI
  **`https://phoenix.lab.orangecluster.nl/oauth2/vault/tokens`**. The route is
  `/oauth2/<idp_name>/tokens`, not `/callback`; Phoenix builds the redirect URI
  it sends from that route, and Vault rejects a mismatch as an opaque
  `invalid redirect_uri`. Use `assignments = ["allow_all"]` per F2's flat-access
  contract (`oidc.tf:22-23`). Then three more edits in the same file:
  a `vault_identity_oidc_key_allowed_client_id` registering the client against
  the `lab` key; an entry appended to `local.oidc_provider_client_ids`
  (`oidc.tf:80-84`); and the new `email` scope added to `scopes_supported`
  (`oidc.tf:100`).
- **`deployments/infrastructure/oidc.tf:55-70`** — add a second
  `vault_identity_oidc_scope` named `email`, modeled on the `groups` scope
  beside it and following the **same** quoting rule: the placeholder is not
  quoted. The template is `{"email":{{identity.entity.metadata.email}}}`.
  Read that block's comment first — its rule is general, not list-specific.
- **`deployments/infrastructure/auth_userpass.tf:38-44`** — add `email` to
  `vault_identity_entity.operator`'s metadata map, sourced from a new variable
  in `deployments/infrastructure/variables.tf`. Without this the scope renders
  an empty claim and Phoenix still fails.
- **`deployments/applications/secrets.tf:11-16`** — `random_password` +
  `vault_kv_secret_v2` for `PHOENIX_SECRET` and `PHOENIX_ADMIN_SECRET` only,
  following the `phoenix_db_credentials` shape already there. Note this is the
  **applications** root, not `deployments/infrastructure/secrets.tf`, which is
  where an earlier draft pointed.
- **The client secret: make it not exist. Register Phoenix as a PUBLIC client
  with PKCE.** This is the recommended route and it deletes the whole problem
  rather than solving it.
  Vault's `lab` provider advertises
  `token_endpoint_auth_methods_supported: ["none", "client_secret_basic",
  "client_secret_post"]` and `code_challenge_methods_supported:
  ["plain", "S256"]` — measured 2026-08-04 by fetching the discovery document
  whose URL §4 gives, and re-measured on the fourth review pass. Phoenix 13.19.2 supports the
  matching pair: its token-endpoint-auth-method setting set to `none`, plus
  its PKCE toggle. **All four settings in the env list below are mandatory on
  this route, not optional**: Vault *requires* PKCE for a public client rather
  than merely permitting it, refusing at both the authorize and the token
  endpoint without it. Phoenix sends `S256`, which matters because the server
  would otherwise default to `plain`. A working public client already runs
  here:
  `deployments/infrastructure/memex_oidc.tf:80` — **the `client_type` line and
  only that line.** Do not copy `assignments` from that block: `:79` binds
  memex's own two tiers, while R4 is a flat-access consumer and uses
  `assignments = ["allow_all"]` as stated above and as `oidc.tf:23-25` names
  it. Copying memex's assignment gates Phoenix login on memex's groups and
  passes `terraform validate`, because that resource lives in the same root.
  **Do not copy that block's TTLs.** `memex_oidc.tf:81-82` sets both to
  `2592000` (30d), which is legal only because its own `memex_human` key
  carries `verification_ttl = 2592000` (`memex_oidc.tf:35`). The shared `lab`
  key is `86400` (`oidc.tf:46`), and a client's `id_token_ttl` may not exceed
  the verification TTL of the key it references, so the apply is refused
  outright. Omit the TTLs or cap them at 86400. With `client_type = "public"` there is no secret to
  store, thread, or rotate, and `client_secret` comes back empty by design.
  **If the operator instead wants a confidential client**, the secret must
  reach the job through **its own KV2 prefix**, following
  `deployments/infrastructure/secrets.tf:90-110` — the `prometheus_bifrost_admin`
  block, which copies credentials from one prefix into the consuming job's own
  so the policy need not widen. Three routes that look plausible and do **not**
  work, each verified against this cluster:
  - **A `templatefile(...)` var.** Writes the secret as a literal into the
    **rendered jobspec**, which is what §6 forbids. It also lands in
    Consul-backed state, but that is not the distinguishing objection: the
    KV2-copy fallback persists it in state too, via `data_json`, as
    `secrets.tf:96-98` says in the repo's own words. The jobspec is the
    difference.
  - **A `template` stanza reading `identity/oidc/client/phoenix` at render
    time.** The Vault side works, but the live `nomad-workloads` policy grants
    only `secret/data/<ns>/<job_id>*` read and `secret/metadata/<ns>/*` list —
    no `identity/*` — so the template blocks on a 403. The `grafana.hcl:79`
    and `phoenix.hcl:61` precedents read **KV2** paths that policy already
    permits, so they are not evidence for this. Making it work would need a
    new `vault_policy`, a new `vault_jwt_auth_backend_role` (per
    `acme.tf:51-90` a dedicated role *replaces* `nomad-workloads` and must
    mirror its `claim_mappings`), and `vault { role = ... }` on the jobspec —
    none of which is in this plan's scope or its "Small. Configuration only."
  - **An ephemeral resource.** The pinned provider has none for this:
    `terraform providers schema` lists only `vault_database_secret` and
    `vault_kv_secret_v2` as ephemeral. And it could not reach the jobspec
    anyway — the repo states the rule at `secrets.tf:96-98`, "ephemeral values
    cannot flow into a non-write-only attribute". An earlier draft of this
    plan cited the applications root's ephemeral posture as support for this
    route; that citation was evidence against it.
  `deployments/applications/services.tf:33-38` remains the model for the
  **cross-root lookup** (`data "vault_identity_oidc_client_creds"` by static
  name, no remote-state link), and `:193` for threading a `client_id`. Copy
  that much regardless of which client type is chosen.
- **`deployments/applications/services/memex.hcl:168-169`** — add the OTLP
  auth header beside the existing tracing settings, templated from the same
  Vault secret Phoenix reads, so the two can never drift. **This file is
  edited in this ticket**, reversing the previous plan's "default
  recommendation does not touch `memex.hcl`".
- **`deployments/infrastructure/services/haproxy.hcl:143`** — delete this one
  line, the shared basic auth on `backend phoenix`. Leave `:153` (mlflow)
  alone.
- **`docs/`** — how to sign in, and the recovery path from Q2.

## 8. Tests & validation gates

### Repo gate

`just pre_commit` runs `pre-commit run --all-files` (`justfile:18-19`) and is
the single loop gate. It validates both `.hcl` (`nomad fmt -recursive`) and
`.tf` (`terraform fmt -check`, plus `scripts/tf_validate.sh` running
`terraform validate` offline against all three roots). The config excludes
`^\.(claude|loop)/`, so this ticket file is not linted. There is no separate
Terraform step to run by hand.

`terraform -chdir=deployments/applications plan` must show the Phoenix job
updated in place and the new secrets added, destroying nothing.

### Evals

The authoritative set is `.loop/evals/R4-rollout-phoenix-oauth2-proxy.md`,
rewritten alongside this plan. The load-bearing rows are the ingest survival
check and the UI gate. **A pass requires the UI to be gated AND ingest to keep
working. Breaking either side is a fail**, unchanged in spirit from the
previous plan even though the mechanism is different.

Note the asymmetry with the old evals: previously ingest passing meant
`/v1/traces` answering **without** auth. Now it means answering **with** a
bearer key, and answering `401`/`403` **without** one.

## 9. Risk assessment

- **Blast radius at apply time: medium, and the failure is silent.** Enabling
  auth stops trace collection instantly if the sender has no key. The UI will
  look correct while observability data is quietly lost, which is the same
  shape of failure as the old plan's port-6006 mistake. It is caught only by
  explicitly testing ingest.
- **Lockout.** Misconfigure the OIDC client, or leave Vault sealed, and nobody
  can log in. Q2 exists for this. Phoenix is less load-bearing during an
  incident than Grafana (G1's version of this risk), but `PHOENIX_ADMIN_SECRET`
  gives a bearer-token way in regardless, which is a genuine advantage of this
  design over the proxy one.
- **`PHOENIX_ADMIN_SECRET` as the ingest credential grants admin to `memex`.**
  It is the only non-interactive option, so it is the recommended v1, but it is
  over-privileged for a trace sender. Q4 records the follow-up.
- **`:latest` means the deployed feature set is unknown.** Auth env var names
  and the OIDC callback path have moved across Phoenix releases. Verify against
  the running container before applying, not against the docs alone.
- **Reversibility: high.** Remove the env settings and Phoenix returns to
  unauthenticated; restore the basic-auth line and the edge gate returns. No
  data migration either way.
- **Reduced risk versus the old plan:** no new job, no proxy, no HAProxy
  path-splitting, and one less unmet dependency (L1).

## 10. Subtickets (ordered, dependency-aware)

1. Confirm the deployed builds. Phoenix's version is one unauthenticated GET
   away — `curl http://192.168.2.29:6006/arize_phoenix_version` — so this step
   is cheap, not open-ended. Confirm against that version: the auth env
   surface, the `/oauth2/<idp>/tokens` callback route, and whether
   `PHOENIX_OAUTH2_VAULT_EMAIL_ATTRIBUTE_PATH` exists. Separately confirm the
   running `memex` image carries the OTLP-headers config field, by inspecting
   the container rather than a vendored path (§4). Pin `phoenix:latest` to a
   digest, or get the operator's agreement that it stays mutable here.
2. **Make Vault able to emit an email claim, before anything else touches
   Phoenix.** The `email` scope (unquoted placeholder — see §4), its entry in
   the provider's `scopes_supported`, and the entity metadata that carries the
   value. A wrong template fails at `terraform apply` rather than silently, so
   this step is self-checking. Then prove the claim actually lands: complete a
   login with an existing client and decode the id_token, or read the `lab`
   provider's `userinfo` endpoint, which applies the same scope templates and
   gives a second way to confirm it. Doing this first means the Phoenix step
   has one unknown instead of two.
3. **Create the Phoenix OIDC client first, in the infrastructure root.** In
   `oidc.tf`: the client with the `/oauth2/vault/tokens` redirect URI, the key
   registration, and the `local.oidc_provider_client_ids` entry. Prefer
   `client_type = "public"` per §7, which removes the secret entirely.
   **This must precede any read of the client**, and an earlier draft of this
   plan had the two steps the other way round. The two roots hold separate
   state with no link between them, so a
   `data "vault_identity_oidc_client_creds"` in the applications root fails
   the whole plan with `no client found at "identity/oidc/client/phoenix"`
   until the infrastructure root has applied. That failure also blocks step 5,
   the memex ingest credential — the step this section calls the thing that
   keeps ingest from going dark.
   Apply the infrastructure root and confirm the client exists before moving
   on.
4. Secrets in the applications root: `PHOENIX_SECRET` and
   `PHOENIX_ADMIN_SECRET` into KV2 as `random_password` values. **Not the OIDC
   client secret** — with a public client there is none, and with a
   confidential one it is Vault-issued and copied into Phoenix's own KV2
   prefix per §7, never generated here and never a `templatefile` var.
5. **Give `memex` the ingest credential**, while Phoenix is still
   unauthenticated. A header Phoenix ignores is harmless; a missing header
   after auth is on drops traces. Ordering this before step 6 is what keeps
   ingest from going dark between applies.
6. Phoenix job env settings, enabling auth. Apply. Confirm the UI gate holds
   server-side (`GET /oauth2/vault/login` returns a 302 to Vault; an
   unauthenticated API call to **the node**, `http://192.168.2.29:6006`,
   returns 401 — probe the node, not the edge, because `haproxy.hcl:143` is
   still in place until step 8 and would answer an edge probe with its own
   401 and a Basic challenge, passing the check for the wrong reason) and that **a trace actually lands**,
   not merely that the POST returns 200.
7. **Check the scheme Phoenix builds its redirect URI from.** HAProxy
   terminates TLS and proxies plain HTTP to `192.168.2.29:6006`
   (`haproxy.hcl:144`), and its `defaults` block (`haproxy.hcl:76-86`) sets no
   `X-Forwarded-Proto` and no `option forwardfor`. Phoenix prefers the browser
   `Referer` and falls back to `request.base_url`, so the fallback path yields
   `http://…/oauth2/vault/tokens`, which Vault rejects against an
   https-registered URI. If it does, add the header at the edge rather than
   registering an http redirect URI. Decide on `PHOENIX_CSRF_TRUSTED_ORIGINS`
   in the same step: the Phoenix docs recommend it when configuring OAuth2
   clients and §7's env list omits it.
8. Remove the HAProxy basic-auth line from the Phoenix backend only
   (`haproxy.hcl:143`).
9. Docs: sign-in, and the Q2 recovery path.
10. Gate and adversarial review. Hand the reviewer the ingest evidence.

## 11. Open questions (forks the operator must settle)

- **Q1 — ANSWERED 2026-07-26, not a fork.** `memex` supports OTLP exporter
  headers, so the ingest credential is a job config change rather than an
  upstream code change. Kept here as a record because the previous plan
  treated ingest auth as impossible and deferred it. The source citations that
  backed this answer pointed into a vendored tree that is not in this checkout
  and have been removed (§4); what remains is verification, not a decision.
  Confirm the env spelling and that the deployed image carries the field, at
  §10 step 1.
- **Q2 — What is the way in if Vault is unavailable?** Phoenix supports local
  username/password accounts alongside OIDC, and `PHOENIX_ADMIN_SECRET` is a
  bearer token that bypasses the login flow. *Recommendation:* keep local
  login enabled and treat `PHOENIX_ADMIN_SECRET` as the break-glass path,
  documented before it is needed. G1 makes the same call for Grafana.
- **Q3 — Flat access, or map Vault groups to Phoenix roles?** F2 defines
  `dashboard-users` among its groups. *Recommendation:* start flat, matching
  the epic's "any successful login is authorized" posture for a
  single-operator lab, and matching G1's Q2. The operator's 2026-07-23
  resolution to gate on `dashboard-users` was made for oauth2-proxy's
  allowed-group setting, which no longer exists in this design; Phoenix's own
  role mapping is the replacement mechanism and is straightforward to add
  later.
- **Q4 — Scoped system key instead of the admin secret, later?**
  `PHOENIX_ADMIN_SECRET` is the only key provisionable without a browser, so
  v1 uses it. Whether a scoped system key can then be minted through Phoenix's
  API using that bearer token is **unverified** and worth one experiment
  before it is promised. *Recommendation:* ship v1 on the admin secret, record
  the privilege concern, and revisit.
- **Q5 — Public client with PKCE, or confidential with a stored secret?
  NEW, and the decision is effectively one-way.** *Recommendation: public.*
  It deletes the client secret entirely, and the secret is what burned two
  earlier review cycles: every route for getting a Vault-issued confidential
  secret into this job is either forbidden by §6, blocked by the
  `nomad-workloads` policy, or unsupported by the pinned provider (§7).
  Phoenix 13.19.2 supports it — its `CLIENT_SECRET` is optional exactly when
  `TOKEN_ENDPOINT_AUTH_METHOD=none`, and PKCE is wired end to end, storing the
  `code_verifier` in a cookie and replaying it at token exchange with `S256`.
  Vault's `lab` provider advertises `none` and `S256` to match.
  **Why it is one-way:** `client_type` is immutable after create
  (`memex_oidc.tf:55-57`), so switching to confidential later means destroying
  and recreating the client, which yields a new `client_id` and requires
  editing `local.oidc_provider_client_ids` (`oidc.tf:80-84`) and the key
  registration alongside it.
  **If the operator picks confidential instead**, one thing this plan does not
  yet assign: §10 step 4 explicitly excludes the client secret and no other
  step claims the KV2 copy, so name the root that writes it before starting.

### Operator fork resolutions carried over from 2026-07-23

The operator settled six forks against the oauth2-proxy design. Their status:

- **Q1 (blocked on L1, per-service dedicated proxy) — SUPERSEDED.** No proxy
  exists in this design, so L1 is no longer a dependency.
- **Q2 (sequence after F2) — STANDS.** F2 still owns the issuer.
- **Q3 (dedicated `phoenix` OIDC client in F2's `oidc.tf`) — STANDS**, and is
  now simpler: the client belongs to Phoenix itself rather than to a proxy in
  front of it. The cross-cutting note fed back into F2, that F2 must provision
  one client per fronted service, still holds for the services that do use
  oauth2-proxy.
- **Q4 (UI-only gate, ingest unauthenticated on the LAN) — SUPERSEDED, and
  reversed.** Phoenix has no unauthenticated-ingest mode once auth is on.
  Ingest becomes authenticated with a bearer key, which is what the old plan
  listed as its deferred follow-up. This is a genuine change to what the
  operator approved and should be re-confirmed.
- **Q5 (TLS-consistent, `--cookie-secure=true`, depend on F3) — STANDS, with
  the dependency retargeted.** F3 is done but superseded by T3, which is what
  actually delivers the trusted cert and the `lab.orangecluster.nl` hostname.
  `depends_on` names T3.
- **Q6 (gate on `dashboard-users`) — SUPERSEDED as written.** See Q3 above.

## 12. Findings for other tickets

Surfaced while rewriting this plan, out of scope here, recorded so they are not
lost:

- **`phoenix:latest` is unpinned** (`phoenix.hcl:53`), the only such image in
  the applications layer, and at odds with the T4 digest-pinning work. It is
  also why this ticket cannot state the deployed auth surface with certainty.
  Deserves its own ticket.
- **`memex`'s edge is open at HAProxy, and always was.** The earlier draft of
  this section said memex sat "behind the same shared `openfang_users` basic
  auth as MLflow, Phoenix, and Bifrost". That was false, not merely stale:
  `backend memex` (`haproxy.hcl:146-147`) has never carried an auth line in any
  revision of the file. What gates memex is its own application auth, and R5
  and R6 have since shipped that: `memex.hcl:138-140` sets API keys and `:167`
  sets `MEMEX_SERVER__AUTH__OIDC`. So the gap this bullet reported is now
  closed by native auth, exactly the shape G1 and this ticket use — but it was
  closed by R5/R6, not by the HAProxy line this section imagined. Nothing left
  to file.
- **F2's consumer contract is one line short.** `oidc.tf:39-40` says appending
  to `local.oidc_provider_client_ids` is "the whole contract; nothing else in
  this file changes". A consumer needing a claim F2 did not ship must also
  extend `scopes_supported` (`oidc.tf:100`), as this ticket does for `email`.
  Worth correcting in F2's comment so the next consumer is not misled.
- **G1 inherits the `email` scope and must not create a second one.** G1
  (Grafana native OIDC) hit the same wall: Vault advertises no email and
  Grafana needs an identity. Once R4 lands, the scope and the
  `scopes_supported` entry exist cluster-wide and G1 consumes them. If G1
  lands first, the ownership reverses and R4 consumes G1's. The two tickets
  must not both create it.
- **Only `vault_identity_entity.operator` will carry an email.** The scope
  emits `identity.entity.metadata.email`, so any human entity added later
  without that metadata key gets an empty claim and is refused at Phoenix's
  callback, with the same `missing_email_scope` error as if the scope did not
  exist. Adding a second human means adding the metadata too. Worth a line in
  `docs/vault-human-auth.md`'s "adding a service" procedure.

## 13. Ticket identity

The slug `R4-rollout-phoenix-oauth2-proxy` now describes the approach this
plan rejects. Every ledger line, eval filename, and future commit subject will
say `oauth2-proxy` for a ticket that deliberately avoids one, which is exactly
the "looks fine, is wrong" pattern A1 exists to catch.

Renaming is safe but manual: no other ticket declares R4 as a dependency
(verified against `.loop/ledger.json`), and `loopctl` has no rename command, so
it means registering `R4-rollout-phoenix-native-oidc`, moving this file and the
eval marker, and dropping the old slug. Recommend doing it before
implementation starts. Operator's call.

## Premises / assumptions

- **P1.** Phoenix authenticates natively and speaks generic OIDC, so no proxy
  is needed. `Evidence:` the Arize authentication doc documents
  `PHOENIX_ENABLE_AUTH`, `PHOENIX_SECRET` and
  `PHOENIX_OAUTH2_<IDP>_{CLIENT_ID,CLIENT_SECRET,OIDC_CONFIG_URL}`. Confirmed
  in the Phoenix source at the version the cluster runs. `probe:` the deployed
  version is one GET away at `/arize_phoenix_version`; §10 step 1 pins it.

- **P2.** Phoenix's OIDC callback route is `/oauth2/<idp_name>/tokens`, not
  `/callback`. `Evidence:` Phoenix's `oauth2` router declares
  `@router.get("/{idp_name}/tokens")` under an `/oauth2` prefix, and every
  vendor docs example uses `<origin-url>/oauth2/<idp>/tokens`. The earlier
  draft's `/callback` literal was wrong and is corrected in §7.

- **P3.** Phoenix hard-requires an `email` claim and always requests
  `openid email profile`. `Evidence:` its config sets that scope list
  unconditionally and its callback raises on an empty JMESPath `email` lookup,
  redirecting to the login page with `error=missing_email_scope`.

- **P4.** Vault silently drops a scope it does not advertise, so the previous
  premise's failure stays invisible until the callback.
  `Evidence:` `docs/vault-human-auth.md:447-449`
  states it for `groups` — Vault "ignores an unsupported scope rather than
  [erroring]", leaving a valid token carrying no claim. The list it is checked
  against is `deployments/infrastructure/oidc.tf:100`, which names `groups`
  alone. §10 step 2 decodes an issued id_token rather than trusting a login
  that appears to succeed.

- **P5.** Vault currently emits no email claim and no entity carries one.
  `Evidence:` `deployments/infrastructure/oidc.tf:100` advertises only
  `scopes_supported = [groups]`; `oidc.tf:55-70` is the sole scope;
  `deployments/infrastructure/auth_userpass.tf:38-44` gives
  `vault_identity_entity.operator` `managed_by` and `kind` metadata and no
  email. This ticket owns closing all three gaps (§4).

- **P6.** F2 is `done` and its issuer is HTTPS, which Phoenix requires.
  `Evidence:` `deployments/infrastructure/oidc.tf:95-101` sets
  `https_enabled = true` with `issuer_host = var.vault_issuer_host`.

- **P7.** A consumer ticket registers itself in a documented way, and the repo
  carries worked examples for both halves R4 needs. `Evidence:` `oidc.tf:28-40`
  describes the key/provider split and `oidc.tf:80-84` is
  `local.oidc_provider_client_ids`. For reading a client's credentials across
  two separate state roots — the part R4 actually reuses — the example is
  `deployments/applications/services.tf:33-38` plus the threading at `:193`.
  `deployments/infrastructure/memex_oidc.tf:70-92` shows the client shape.
  One difference R4 must **not** copy: it registers against its own
  `memex_human` key (`memex_oidc.tf:72`), while R4 uses the shared `lab` key
  (`oidc.tf:136`). The other difference — that memex is a **public** client —
  is the part §7 recommends R4 copy deliberately, because it removes the
  client secret entirely.

- **P8.** Two HAProxy backends still carry shared basic auth, and Bifrost is
  not one of them. `Evidence:`
  `deployments/infrastructure/services/haproxy.hcl:143` (phoenix) and `:153`
  (mlflow) are the only `http-request auth` lines; `backend bifrost`
  (`:156-157`) is a bare `server` line since B1's commit `ac3267b`.

- **P9.** `backend memex` (`haproxy.hcl:146-147`) has no auth line and never
  had one; memex is gated by its own application auth.
  `Evidence:` `deployments/applications/services/memex.hcl:138-140` sets API
  keys and `:167` sets `MEMEX_SERVER__AUTH__OIDC` (shipped by R5 and R6, both
  `done`).

- **P10.** The Phoenix job is one env template away from carrying these
  settings. `Evidence:`
  `deployments/applications/services/phoenix.hcl:57` is `vault {}`, `:59-66`
  the single existing env template, `:53` the `:latest` image, `:54`
  `network_mode = "host"`, `:12-17` the two static ports. The job is rendered
  from `deployments/applications/services.tf:125-134`.

- **P11.** `GET /` on Phoenix returns 200 SPA HTML even with auth enabled, so
  a redirect-based UI gate check is the wrong probe. `Evidence:` Phoenix is a
  single-page app whose static handler falls back to `index.html` with an
  `authentication_enabled` context flag; the gate is applied client-side and
  on the API/GraphQL layer. The eval rows that expected a 302 on `/` are
  rewritten (§8).

- **P12.** The repo gate is `just pre_commit`. `Evidence:` `justfile:18-19` is
  `pre_commit: pre-commit run --all-files`; `.pre-commit-config.yaml:1`
  excludes `^\.(claude|loop)/`, so this ticket file is not linted.

- **P13.** No other ticket declares R4 as a dependency, so the §13 rename is
  safe. `Evidence:` checked against every `depends_on` in the ledger.

- **P14 (UNCERTAIN).** The redirect URI Phoenix builds behind the TLS edge is
  https. `Evidence against:` HAProxy's `defaults` block
  (`haproxy.hcl:76-86`) sets no `X-Forwarded-Proto` and no `option
  forwardfor`, and it proxies plain HTTP to `192.168.2.29:6006`
  (`haproxy.hcl:144`). The browser `Referer` path should yield https; the
  fallback yields http. §10 step 7 checks it rather than assuming.

- **P15. VERIFIED 2026-08-04.** The deployed `memex` image carries the OTLP
  exporter headers config field: `TracingConfig.headers: dict[str, str]`
  exists in the running container. This premise was UNCERTAIN through three
  review cycles because the vendored source that evidenced it is absent from
  the checkout (§4); the fourth pass confirmed it against the container
  itself. §10 step 1 still re-checks it, since the image tag can move.

## Plan review history

### 2026-07-30 (A1 premise sweep) — PARTIALLY SOUND, `fail`

Reviewed by `loop-plan-reviewer` against the repo and the live cluster as part
of `A1-audit-plan-premise-sweep`. The verdict is
`.loop/verdicts/R4-rollout-phoenix-oauth2-proxy.plan-validator.md`.

The approach survived: Phoenix's own OIDC client against Vault, no proxy. Three
things sank the plan as written. Phoenix hard-requires an `email` claim that
Vault emits for nobody and silently drops the scope for, so a correct
implementation would apply cleanly, redirect to Vault, complete the login, and
die at the callback. The redirect URI literal in §7 was wrong. And two eval
rows failed a correct implementation, pushing an implementer back toward the
proxy the rewrite had removed.

### 2026-08-04 — required fixes applied

All six required fixes are in, re-checked against the repo as it stands now
rather than as the verdict found it on 2026-07-30. F2 has since landed, which
changes several answers.

1. **The email claim is now the ticket's spine**, not a missing assumption.
   §4 has a section on it, §6 requirements 6 and 7 make it binding, §7 names
   all three edits (scope, `scopes_supported`, entity metadata), and §10 step 2
   does it first and proves it by decoding a token. The template placeholder is
   **unquoted**, the same rule as the `groups` scope beside it — an earlier
   draft of this section claimed the opposite and was wrong. R4 owns this
   work: F2 is `done` and shipped only `groups`.
2. **Redirect URI corrected** to `.../oauth2/vault/tokens` in §7, and §6
   requirement 7 states why the wrong value fails opaquely. §7 also now lists
   the key registration and the `local.oidc_provider_client_ids` append, per
   F2's documented consumer contract.
3. **Eval rows rewritten** to probe something server-side, with an explicit
   assertion that `GET /` returning 200 SPA HTML is expected, so nobody
   "fixes" it by reintroducing a proxy.
4. **Stale HAProxy claims fixed.** Bifrost lost its basic-auth line to B1 on
   2026-07-29; only phoenix `:143` and mlflow `:153` remain. §12's memex claim
   was false rather than stale and is corrected: that backend never had an auth
   line, and R5/R6 have since given memex native auth.
5. **Anchors repaired.** `services.tf:97-107` to `:125-134`; `phoenix.hcl:6-9`
   to `:54` for `network_mode`; the phoenix secrets pointer moved from
   `deployments/infrastructure/secrets.tf` to
   `deployments/applications/secrets.tf:11-16`; `memex.hcl:142-143` to
   `:168-169`. The `apm.yml` and `apm_modules/...` citations are **deleted**,
   not repaired: that tree is gitignored and absent from this checkout, so an
   implementer cannot open it. The capability it evidenced is now an explicit
   UNCERTAIN (P15) verified at step 1.
6. **Scheme check added** as §10 step 7, together with the
   `PHOENIX_CSRF_TRUSTED_ORIGINS` decision.

Structural: the plan now carries the `# Ticket:` header and a
`Premises / assumptions` section.

### 2026-08-04, second pass — PARTIALLY SOUND, `pass-with-required-fixes`

The eight fixes above were checked against the deployed versions — Vault
**2.0.3**, Phoenix **13.19.2** — rather than from memory. Fix 1 was confirmed
correct, not merely inverted: a `map[string]string` lookup returns
`strconv.Quote(...)` while the `[]string` arm does not, so both scopes take an
unquoted placeholder, and scope creation validates against an empty entity so
the wrong form is rejected at apply time. `email` is not a reserved claim, so
the approach is viable at all. All fifteen premises hold or are honestly
UNCERTAIN.

Four more fixes, **two of them defects the previous round's fixes
introduced**. All now applied.

1. **A contradiction left in the changelog.** This section still described the
   quoting trap as "the inverse of the `groups` case" while the three
   instruction sites said the opposite. The instructions were right; the
   changelog is corrected. A reader who trusted the summary would have
   reintroduced the original bug.
2. **Eval row 3 used `curl -sI`, which sends HEAD, and HEAD cannot work
   here.** FastAPI does not add HEAD to a GET route, so Phoenix's SPA
   catch-all answers every HEAD with `200 text/html`. Measured 2026-08-04:
   `GET /arize_phoenix_version` returns `200 text/plain` while
   `HEAD /arize_phoenix_version` and `HEAD /definitely-not-a-route` both
   return `200 text/html`. The row could not distinguish a wired route from a
   nonexistent one, and failed a correct implementation — the same defect
   class as cycle 1, in the fix meant to cure it. Every HEAD probe in the
   marker is now a GET.
3. **The client-secret guidance pointed at an example that carries no
   secret.** `services.tf:33-38` reads a **public** client
   (`memex_oidc.tf:80`), whose `client_secret` comes back empty by design, and
   `:193` threads only the public `client_id`. Copying that shape for
   Phoenix's confidential client would write the secret as a literal into the
   rendered jobspec and into Consul-backed Terraform state, breaking §6's own
   KV2 restriction. §7 now says to copy the lookup but not the handling, and
   names the alternatives.
4. **Eval row 2 probed the edge, where HAProxy answers first.** Measured
   2026-08-04: `https://phoenix.lab.orangecluster.nl/graphql` returns `401`
   with `www-authenticate: Basic realm="phoenix"`, while the node returns
   `200`. The row passed before the ticket did anything and would keep passing
   if Phoenix's own gate were never enabled. It now probes the node and
   asserts the absence of the Basic challenge, matching what the ingest rows
   already did.

### 2026-08-04, third pass — PARTIALLY SOUND, `fail`

F1, F2 and F4 all held under re-checking, and P15 was upgraded from UNCERTAIN
to verified in the plan's favor: `TracingConfig.headers: dict[str, str]` does
exist in the running memex container. Twelve of fifteen premises hold, two are
honestly UNCERTAIN. **F3 was the failure**, and it failed by prescribing two
routes that cannot be followed.

1. **Both of F3's named routes are dead ends**, each disproved against the
   live cluster.
   - *A `template` stanza reading the client secret at render time.* The Vault
     half works, but the live `nomad-workloads` policy grants no `identity/*`
     access at all, so the template blocks on a 403. The two precedents F3
     cited (`grafana.hcl:79`, `phoenix.hcl:61`) read KV2 paths the policy
     already permits, so they were never evidence for this. Making it work
     needs a new policy, a new JWT role that must mirror `claim_mappings`
     because a dedicated role *replaces* `nomad-workloads`, and
     `vault { role = ... }` on the jobspec — far outside "Small.
     Configuration only."
   - *An ephemeral resource.* The pinned provider offers ephemeral variants
     only for `vault_database_secret` and `vault_kv_secret_v2`, and
     `terraform validate` rejects
     `ephemeral "vault_identity_oidc_client_creds"` outright. Even with one,
     `secrets.tf:96-98` states the blocking rule in the repo's own words:
     "ephemeral values cannot flow into a non-write-only attribute." F3 cited
     the applications root's ephemeral posture as support for this route; that
     citation was evidence against it.
   With `templatefile` vars already forbidden, F3 left no usable route at all.
2. **The route that works was unnamed**, and so was the option that removes
   the problem. §7 now recommends a **public client with PKCE** — Vault's
   `lab` advertises `none` and `S256`, Phoenix 13.19.2 supports the matching
   token-endpoint-auth-method and PKCE settings, and
   `deployments/infrastructure/memex_oidc.tf:70-83` is a working public client
   here — so there is no secret to handle. For a
   confidential client it names the KV2-copy pattern at `secrets.tf:90-110`.
3. **§10's ordering was broken by the F3 edit.** Step 3 read the client's
   credentials from the applications root while step 4 created the client in
   the infrastructure root: separate states, no link. Verified live —
   `terraform plan` fails with `no client found at
   "identity/oidc/client/phoenix"`, which also blocks the memex ingest
   credential, the step this plan calls the thing that keeps ingest from going
   dark. Client creation is now step 3 and the secrets step is 4.
4. **One leftover from F2:** eval row 8's Scorer column still said `curl -sI`
   while its Input was a GET, contradicting the previous changelog entry.

### 2026-08-04, fourth pass — PARTIALLY SOUND, `fail`

**The headline question came back in the plan's favor.** Phoenix 13.19.2
genuinely supports a public client with no secret, verified against the exact
wheel for the deployed version rather than the docs: `CLIENT_SECRET` is
optional precisely when `TOKEN_ENDPOINT_AUTH_METHOD=none`, and PKCE is wired
end to end — the `code_verifier` is stored in a cookie and replayed at token
exchange with `S256`. Vault's `lab` provider advertises `none` and `S256` to
match. So the pass-3 recommendation is real and not a fourth dead end. §10's
reordering was traced step by step and holds: no cross-root read precedes its
write. The KV2-copy fallback was confirmed followable, and the
`nomad-workloads` policy confirmed to grant `secret/data/<ns>/<job_id>/*` with
no `identity/*`, which is both why the template route is dead and why the
fallback works.

What failed was internal contradiction, all of it introduced by the pass-3
fixes. Seven fixes, applied:

1. **P7 forbade what §7 recommends.** P7 listed the public client type as one
   of two things "R4 must not copy" from memex while §7 recommended exactly
   that. An implementer trusting the Premises section would have gone
   confidential and re-entered the problem that burned two cycles. P7 now
   keeps only the key warning, which is correct and load-bearing.
2. **§7's env list was still the confidential shape** — "the three
   `PHOENIX_OAUTH2_VAULT_*` settings". The recommended route needs four and
   `CLIENT_SECRET` is not among them. This was a positive assertion that is
   wrong, not a deferred spelling, and following it is a hard boot failure:
   `CLIENT_SECRET` is required whenever `TOKEN_ENDPOINT_AUTH_METHOD` is unset,
   and Vault issues no secret for a public client. All four are now named.
3. **The block §7 said to copy fails at apply.** `memex_oidc.tf:81-82` sets
   30-day TTLs, legal only against its own key's `verification_ttl`. The
   shared `lab` key is 86400 and the mismatch is refused outright. The
   citation now points at `:78-80` and says to omit or cap the TTLs.
4. **The public-versus-confidential choice lived only in §7.** It is now Q5 in
   Open Questions, with the recommendation and the warning that `client_type`
   is immutable, so the choice is effectively one-way. Q5 also flags the one
   thing unassigned on the confidential branch: which root writes the KV2
   copy.
5. **§10 step 6 did not say node or edge.** At that point `haproxy.hcl:143` is
   still present, so an edge probe is answered by HAProxy with a 401 and a
   Basic challenge and passes for the wrong reason — the identical defect the
   second pass fixed in eval row 2.
6. **§6 requirement 4 under-stated the complexity rule.** Phoenix applies it
   to `PHOENIX_SECRET` as well as `PHOENIX_ADMIN_SECRET`, so `min_lower` and
   `min_numeric` belong on both `random_password` resources or a later
   rotation can produce a value Phoenix refuses at boot.
7. **P15 read `(UNCERTAIN)` while the changelog claimed it verified.** The
   fourth pass settled it in the plan's favor: the field does exist in the
   running container.

Two smaller notes also applied: §7's pointer for the discovery values now says
they were measured rather than citing §4, which carries the URL but not the
output; and the objection to a `templatefile` var is narrowed to the rendered
jobspec, since the KV2-copy fallback persists the secret in state too.

**A bonus finding the plan never claimed.** Phoenix also requests `profile`,
which Vault does not advertise. That is harmless, and P4 now rests on primary
evidence rather than this repo's documentation: Vault's authorize handler
carries the comment that scope values unsupported by the provider are ignored.

### 2026-08-04, fifth pass — PARTIALLY SOUND, `pass-with-required-fixes`

**The headline attack came back clean, and the route is more correct than the
plan claimed.** §7's four env settings are exactly what Phoenix 13.19.2
parses, verified against the wheel matching the deployed version:
`USE_PKCE=true` is right and `1` would raise; `OIDC_CONFIG_URL` is required
unconditionally, with no public-client exemption; and `none` is a valid
token-endpoint-auth-method, which is precisely where `CLIENT_SECRET` becomes
optional. Better still, Vault **requires** PKCE for public clients rather than
merely permitting it, refusing at both the authorize and token endpoints, and
Phoenix sends `S256` where the server would otherwise default to `plain`. So
all four settings are mandatory, which §7 now says.

Also confirmed: Q5's immutability claim holds and contradicts neither §7 nor
P7 — all three recommend public. F5's §10 edit is consistent, and step 6 must
probe the node precisely because step 8 removes `haproxy.hcl:143` after it.
F6 is right: both secrets go through the same complexity requirements.

**One defect, and it is the pattern this batch keeps producing: a fix
contradicting a section it did not touch.** The previous round narrowed the
memex citation to `:78-80` and called "the `assignments` and `client_type`
lines" the part to copy. But `:79` binds memex's own two tiers, while two
bullets earlier the same section says `assignments = ["allow_all"]`, and
`oidc.tf:23-25` names R4 explicitly as a flat-access consumer. Two values for
one attribute in one section, with nothing saying which wins — and copying
`:79` gates Phoenix login on memex's groups while passing `terraform validate`,
since that resource lives in the same root. Narrowing the citation from a
shape reference to specific lines is what turned `assignments` into a named
line to copy. It now names `client_type` and only `client_type`. The TTL half
of that fix was correct and is unchanged.

Also applied: §4 still carried "a Phoenix client plus three env vars", the
phrasing the fourth pass removed from §7, in the section an implementer reads
first.

### 2026-08-04, sixth pass — SOUND, `pass-with-required-fixes`

**Premise now SOUND.** All four attacks came back clean. The `assignments`
fix is unambiguous — `assignments` appears three times in the plan and all
three say `allow_all`. Items 3 and 4 are accurate and item 3 is stronger than
"correct": Vault refuses at **both** the authorize and the token endpoint with
the same "PKCE is required for public clients" message; the server default is
`plain` and Phoenix always sends `S256`; `USE_PKCE` raises on `1`; and
`OIDC_CONFIG_URL` is required *before* the auth-method branch, so there is no
public-client exemption. §10 reads consistently end to end, with no step
reading what a later step writes.

Three fixes, all one-line, **all in §2 — the one section five passes never
audited.** Its opening paragraph was byte-identical to the pre-review
2026-07-26 draft, so it still described the confidential-client design the
third pass removed:

1. **"three secrets in KV2"** — the design provisions two. The third was the
   client secret, which §7 and §10 step 4 both now exclude. Left as written it
   seeds exactly the failure §7 spends a paragraph preventing: an implementer
   hunting for a secret that does not exist.
2. **"no HAProxy auth change"** — false. Requirement 3 makes deleting
   `haproxy.hcl:143` binding and §10 step 8 is that step. §9's parallel
   sentence already had it right.
3. **"see P15 — this is UNCERTAIN"** — P15 reads `VERIFIED 2026-08-04`. §4
   carried the same stale wording. This is the fourth pass's P15 fix left
   behind in the two sections that point at it.

The lesson this batch keeps re-teaching: a fix applied at the site a reviewer
names leaves every *other* site that asserts the same fact stale, and §2 is
the section an implementer sizes the work from.
