---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider", "T3-tls-edge-cutover-lab-domain", "A1-audit-plan-premise-sweep"]
priority = 5
summary = "Turn on Phoenix's own authentication and point its generic OIDC client at Vault, instead of fronting it with oauth2-proxy. Phoenix speaks OIDC natively and authenticates OTLP ingest with a bearer key on the same port, so the port-6006 split, the extra proxy job, and the L1 dependency all disappear. Enabling auth blocks ingest until the sender presents a key, so the memex job gains an OTLP auth header in the same change."
tags = ["phoenix", "oidc", "vault", "terraform", "otlp"]
---

# R4 — Sign in to Phoenix with Vault OIDC, natively

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

## 1. Title

Enable Phoenix's built-in authentication and point its generic OIDC client at
Vault's OIDC provider, so a browser must complete a Vault login to reach the
Phoenix console, and authenticate OTLP trace ingest with a bearer key rather
than leaving it open. No proxy in front of Phoenix.

## 2. Size / Effort

**Small.** Configuration only on both sides: a handful of `PHOENIX_*` env
settings in an existing Vault-templated block, one OIDC client in Terraform,
three secrets in KV2, and one added env line on the `memex` job. No new job, no
proxy, no HAProxy auth change, no application code.

Turning auth on **blocks all trace ingest until the sender presents a key**, so
the `memex` side is not optional. It is a one-line job change: `memex` already
supports OTLP exporter headers (§4, verified in source). The remaining effort
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

## 4. Context (today's state)

Verified 2026-07-26 against the repo and the running cluster.

- **Phoenix runs under `applications/`, not `infrastructure/`.** The job is
  `deployments/applications/services/phoenix.hcl`, rendered by
  `deployments/applications/services.tf:97-107` with `phoenix_host =
  "192.168.2.29"`. It runs `network_mode = "host"` on `orangepi4a`
  (`phoenix.hcl:6-9`) and is live: `curl http://192.168.2.29:6006/healthz`
  returns `200`. Re-read for current line numbers.
- **The job has exactly one env template today** (`phoenix.hcl:59-66`),
  injecting `PHOENIX_SQL_DATABASE_URL` from Vault KV2. It already carries a
  `vault {}` stanza (`phoenix.hcl:57`). This is the block the new settings
  extend; no new mechanism is required. Phoenix is already Postgres-backed,
  which is where it stores its user table.
- **Two static ports** (`phoenix.hcl:12-17`): `6006` serves the web UI **and**
  the HTTP OTLP collector (`/v1/traces`); `4317` serves gRPC OTLP.
- **`memex` is the only in-repo trace sender.** `memex.hcl:142-143` sets
  `MEMEX_SERVER__TRACING__ENABLED=true` and
  `MEMEX_SERVER__TRACING__ENDPOINT=http://${phoenix_host}:6006/v1/traces`. The
  job sets no header today, but **`memex` supports one**, verified in the
  vendored source at `apm_modules/JasperHG90/memex`:
  - `TracingConfig.headers: dict[str, str]`
    (`packages/common/src/memex_common/config.py:1542-1545`), described as
    "Optional headers for the OTLP exporter (e.g. auth tokens)".
  - Passed straight through to the exporter:
    `OTLPSpanExporter(endpoint=config.endpoint, headers=config.headers or
    None)` (`packages/core/src/memex_core/tracing.py:46-49`).

  So the ingest credential is a **job config change, not an upstream code
  change**. Two caveats the implementer must confirm rather than assume:
  - The env spelling follows the existing `__` nesting convention, so
    `MEMEX_SERVER__TRACING__HEADERS`, supplied as a JSON object because the
    field is a `dict`. **Confirm the exact form pydantic-settings accepts in
    the deployed build before applying**, since a silently unparsed value
    means traces stop.
  - The vendored copy is pinned at `apm.yml:2` (`version: 2a053a7`) and may
    lag the deployed `memex-jetson` image. Check the running build has the
    field.
- **Phoenix's image is the mutable tag `docker.io/arizephoenix/phoenix:latest`
  (`phoenix.hcl:53`).** Nobody can tell from the repo which Phoenix version is
  running, and OIDC role mapping and auth env vars vary by version. It is also
  the only unpinned image in the applications layer, which sits at odds with
  the T4 digest-pinning commit. Pinning it is out of scope here (§5) but is a
  precondition the implementer should raise, not silently absorb.
- **HAProxy** (`deployments/infrastructure/services/haproxy.hcl`) routes
  Phoenix by host ACL to a backend that applies shared basic auth
  (`http-request auth unless { http_auth(openfang_users) }`) against the
  `openfang_users` userlist. MLflow and Bifrost use the same line. Post-T3 the
  edge serves TLS and the hostname is `phoenix.lab.orangecluster.nl`.
  **Re-read the file for current line numbers: T3 rewrites this frontend.**
- **Vault's OIDC provider does not exist yet.** F2 creates the issuer, key,
  scopes and clients in `deployments/infrastructure/oidc.tf`. F2's declared
  clients do not include Phoenix. This ticket adds one.

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
- Removing HAProxy's shared basic auth from MLflow or Bifrost. Only the Phoenix
  line is touched.
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
3. The HAProxy shared basic-auth line on the Phoenix backend is **removed**,
   not stacked on top of Phoenix's own login. Leave MLflow and Bifrost alone.
4. `PHOENIX_SECRET` and `PHOENIX_ADMIN_SECRET` are distinct values, both
   generated by Terraform `random_password` and stored in Vault KV2, never
   committed. `PHOENIX_ADMIN_SECRET` must satisfy the documented complexity
   rule (>=32 chars, >=1 digit, >=1 lowercase), which `random_password` does not
   guarantee by default: set `min_lower` and `min_numeric` explicitly.
5. A way in that does not depend on Vault survives, or its absence is an
   explicit operator decision. See Q2.

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
  `PHOENIX_ADMIN_SECRET`, the three `PHOENIX_OAUTH2_VAULT_*` settings, and
  `PHOENIX_USE_SECURE_COOKIES` (post-T3 the edge is HTTPS). Values come from
  Vault, not literals.
- **`deployments/applications/services.tf:97-107`** — thread the new Vault
  secret paths into the Phoenix `templatefile(...)` var map, following the
  `phoenix_secret` var already there.
- **`deployments/infrastructure/oidc.tf`** (created by F2) — add a
  `vault_identity_oidc_client` for Phoenix with redirect URI
  `https://phoenix.lab.orangecluster.nl/oauth2/vault/callback` (**confirm the
  exact callback path against the deployed Phoenix version before applying**;
  it is version-dependent and a mismatch presents as an opaque provider-side
  error), plus its assignment.
- **`deployments/infrastructure/secrets.tf`** — `random_password` +
  `vault_kv_secret_v2` for the OIDC client secret, `PHOENIX_SECRET`, and
  `PHOENIX_ADMIN_SECRET`, following the existing shape in that file.
- **`deployments/applications/services/memex.hcl:142-143`** — add the OTLP
  auth header beside the existing tracing settings, templated from the same
  Vault secret Phoenix reads, so the two can never drift. **This file is
  edited in this ticket**, reversing the previous plan's "default
  recommendation does not touch `memex.hcl`".
- **`deployments/infrastructure/services/haproxy.hcl`** — remove the shared
  basic-auth line from the Phoenix backend only. Re-read for line numbers,
  T3 rewrites this file.
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

1. Confirm the deployed builds: which Phoenix version is behind `:latest` and
   its auth env surface plus callback path, and that the running `memex` image
   carries `TracingConfig.headers`. Pin `phoenix:latest` to a digest, or get
   the operator's agreement that it stays mutable for this ticket.
2. Secrets in Terraform: OIDC client secret, `PHOENIX_SECRET`,
   `PHOENIX_ADMIN_SECRET`, into KV2.
3. Phoenix OIDC client in F2's `oidc.tf`, with the verified callback path.
4. **Give `memex` the ingest credential first**, while Phoenix is still
   unauthenticated. A header Phoenix ignores is harmless; a missing header
   after auth is on drops traces. Ordering this before step 5 is what keeps
   ingest from going dark between applies.
5. Phoenix job env settings, enabling auth. Apply. Confirm the UI redirects to
   Vault and that **a trace actually lands**, not merely that the POST
   returns 200.
6. Remove the HAProxy basic-auth line from the Phoenix backend only.
7. Docs: sign-in, and the Q2 recovery path.
8. Gate and adversarial review. Hand the reviewer the ingest evidence.

## 11. Open questions (forks the operator must settle)

- **Q1 — ANSWERED 2026-07-26, not a fork.** `memex` supports OTLP exporter
  headers (`config.py:1542-1545`, `tracing.py:46-49`), so the ingest
  credential is a job config change. Kept here as a record because the
  previous plan treated ingest auth as impossible and deferred it. What
  remains is verification, not a decision: confirm the env spelling and that
  the deployed image carries the field (§4).
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
- **`memex`'s edge auth was never assigned.** `memex` is routed at the HAProxy
  edge behind the same shared `openfang_users` basic auth as MLflow, Phoenix,
  and Bifrost, and no rollout ticket covers replacing it. This is the same gap
  G1 found for Grafana. If `memex` supports OIDC for humans and workload
  identities in a build newer than the vendored pin, the fix is native auth
  like G1 and this ticket, not oauth2-proxy. Worth its own ticket; confirm the
  capability against the current `memex` release first, since the vendored
  copy at `apm.yml:2` shows API-key auth only
  (`packages/core/src/memex_core/server/auth.py:1,52-61`).

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
