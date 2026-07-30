---
verdict: fail
---

# R4-rollout-phoenix-oauth2-proxy — plan-validator

Plan fingerprint verified locally: `sha256sum .loop/plans/R4-rollout-phoenix-oauth2-proxy.md`
= `a5f8dc057d25bbbd4b56211fa8c9ff2ba9b1981c85a6229ef4b69aab8cf26514`, matching
the briefing. The `plan:` line is omitted because this is a `fail` and must not
authorize the flip to `ready`.

Note on the briefing: the plan was **rewritten 2026-07-26**, not left at its
2026-07-24 form. The rewrite already caught and reversed the "Phoenix has no
native auth" premise the dispatch predicted, and did so correctly. The breaks
below are in the *new* design.

## Premise verdict: PARTIALLY SOUND (severity: fail)

The chosen approach (Phoenix's own generic OIDC client against Vault, no
oauth2-proxy) is correct and survives review. Three things sink the plan as
written: the login flow cannot complete with what F2 delivers, the redirect URI
literal in the code surface is wrong, and two of the eval's load-bearing rows
fail a correct implementation.

## Assumptions

### P1 — Phoenix supports native authentication and a generic OIDC client, so no proxy is needed. HOLDS
Arize docs (fetched live from
`https://arize.com/docs/phoenix/self-hosting/features/authentication`) document
`PHOENIX_ENABLE_AUTH`, `PHOENIX_SECRET`, and
`PHOENIX_OAUTH2_<IDP>_{CLIENT_ID,CLIENT_SECRET,OIDC_CONFIG_URL}`. The reversal
in the 2026-07-26 rewrite is right.

### P2 — The deployed Phoenix build carries that surface. HOLDS (and the plan understates what is knowable)
`curl http://192.168.2.29:6006/arize_phoenix_version` returns **13.19.2**. At
`Arize-ai/phoenix@arize-phoenix-v13.19.2`, `src/phoenix/config.py:321` defines
`ENV_PHOENIX_ADMIN_SECRET`, `:295` `PHOENIX_DISABLE_BASIC_AUTH`, `:342`
`PHOENIX_USE_SECURE_COOKIES`, and `:2254-2332` the `PHOENIX_OAUTH2_<IDP>_*`
surface including `SCOPES` and `EMAIL_ATTRIBUTE_PATH`. `PHOENIX_ADMIN_SECRET`'s
documented rules (>=32 chars, >=1 digit, >=1 lowercase, differs from
`PHOENIX_SECRET`, usable as `Authorization: Bearer`) are confirmed in the docs
and enforced at `config.py:1180-1196`.

Two corrections to §4/§9: (a) "Nobody can tell from the repo which Phoenix
version is running" is true of the repo but the running version is one
unauthenticated GET away, so §10 step 1 is cheap, not open-ended; (b) the docs
the plan quotes describe a **newer** Phoenix than the deployed one (they
reference "Through Phoenix 18", and the documented "always available"
`GET /auth.md` returns the SPA shell, not Markdown, on 192.168.2.29:6006), so
capability claims must be read per-version, as the plan does require.

### P3 — The OIDC redirect URI is `https://phoenix.lab.orangecluster.nl/oauth2/vault/callback`. BREAKS
The route is `/oauth2/<idp_name>/**tokens**`. At v13.19.2,
`src/phoenix/server/api/routers/oauth2.py:79-81` sets `APIRouter(prefix="/oauth2")`
and `:145` declares `@router.get("/{idp_name}/tokens")`; the redirect URI Phoenix
sends to the IdP is built from that route (`oauth2.py:115`, `:864-871`). Every
docs example agrees (`<origin-url>/oauth2/google/tokens`,
`<origin-url>/oauth2/aws_cognito/tokens`). §7 hands the implementer a literal
that is wrong; the hedge "confirm the exact callback path" does not repair a
wrong value in the code surface, and Vault rejects the mismatch as an opaque
`invalid redirect_uri`.

### P4 — Vault's OIDC provider publishes a well-known configuration Phoenix can consume. HOLDS, narrowly
Live read: `GET http://192.168.2.30:8200/v1/identity/oidc/provider/default/.well-known/openid-configuration`
returns a valid discovery document. But it advertises
`"scopes_supported": ["openid"]` and `"claims_supported": []`. Note also
`PHOENIX_OAUTH2_<IDP>_OIDC_CONFIG_URL` must be HTTPS except for localhost
(`config.py:1469-1483`), so R4 depends on F2 setting an `https://vault.lab...`
issuer; the live issuer is still `http://192.168.2.30:8200/...`.

### P5 — A Vault OIDC client plus Phoenix's three env vars is enough for a browser login. BREAKS (most dangerous)
Phoenix **always** requests `openid email profile` — `config.py:1523`
(`scopes = ["openid", "email", "profile"]`), and the docs state the baseline
"cannot be removed" — and it **hard-requires an `email` claim** to identify the
user: `oauth2.py:439-450` raises `MissingEmailScope` when the JMESPath
`email` lookup is empty, and `:237-239` turns that into a redirect to the login
page with `error=missing_email_scope`.

Vault does not error on unknown scopes, it **silently drops them**:
`vault/identity_store_oidc_provider.go:1751-1757` keeps only scopes present in
`provider.ScopesSupported`. So the authorize call succeeds, and the ID token and
`/userinfo` come back with no `email` claim, and login dies at Phoenix's callback
with a generic error. Making it work needs a `vault_identity_oidc_scope` named
`email` whose template emits an email claim (`openid` is reserved,
`identity_store_oidc_provider.go:893-895`), that scope added to the provider's
`scopes_supported`, and a Vault identity entity actually carrying the email
value. None of that appears in §7, §10, or §11.

### P6 — Dependency F2 delivers what this plan needs from the issuer. BREAKS
F2's plan promises "a scope with a claim template that exposes the group/entity
claim relying parties (MinIO, oauth2-proxy) read"
(`.loop/plans/F2-foundation-vault-oidc-provider.md:114-116`) and clients for
oauth2-proxy and the MinIO console tiers (`:117-119`) — no email scope, and no
Phoenix client (which R4 correctly says it adds itself). F2 also leaves entity
and alias wiring conditional on an unresolved auth-backend fork ("F2 creates the
identity groups and, if the operator picks a backend, the entity-alias wiring;
otherwise it leaves groups with no members", `:95-96`). This is the M1/F1
template exactly: R4 needs an email-bearing OIDC identity, F2 delivers a
group-claim scope and possibly no entities.

Secondary gap in the same edge: F2 wires `allowed_client_ids` on the key and the
provider (`F2 …:145-154`); adding a Phoenix client means amending both lists.
§7 mentions only the client and its assignment.

### P7 — `memex` can carry an OTLP auth header as configuration. HOLDS in source, UNCERTAIN for the deployed image
Verified in the vendored copy: `TracingConfig.headers` at
`apm_modules/JasperHG90/memex/packages/common/src/memex_common/config.py:1542-1545`
with the quoted description, and passed through at
`packages/core/src/memex_core/tracing.py:46-49`. The deployed job runs
`ghcr.io/jasperhg90/memex-jetson:1.1.0` (`nomad job inspect memex`) and I could
not confirm that build carries the field. The plan already flags both this and
the pydantic-settings spelling as things to verify, so this is an honest
UNCERTAIN, not a defect.

### P8 — HAProxy gates Phoenix with shared basic auth, and "MLflow and Bifrost use the same line". BREAKS (stale premise)
Phoenix and MLflow still do:
`deployments/infrastructure/services/haproxy.hcl:142-143` and `:152-153`,
confirmed identical in the live config (`nomad job inspect haproxy`). **Bifrost
does not**: commit `ac3267b` (B1, 2026-07-29, three days after this rewrite)
deleted `http-request auth unless { http_auth(openfang_users) }` from
`backend bifrost`; the backend is now `haproxy.hcl:156-157` with a bare `server`
line. §4's claim and §5's non-goal "Removing HAProxy's shared basic auth from
MLflow or Bifrost" are stale.

### P9 — §12: "`memex` is routed at the HAProxy edge behind the same shared `openfang_users` basic auth as MLflow, Phoenix, and Bifrost". BREAKS (false, not merely stale)
`backend memex` (`haproxy.hcl:146-147`) has never carried an auth line — checked
against every revision of the file back to `b629230`. memex's edge is
*unauthenticated at HAProxy* and relies solely on its own API keys
(`memex.hcl:138-140`). The follow-up ticket §12 proposes would be scoped from a
false starting state, and the true state is more urgent than described.

### P10 — Post-T3 the edge is TLS at `phoenix.lab.orangecluster.nl`. HOLDS
`haproxy.hcl:95-96` (`bind *:443 ssl crt /secrets/haproxy.pem`), `:91-93` (:80
redirects to https), `:103` (`acl is_phoenix hdr(host) -i
phoenix.lab.orangecluster.nl`), `:114`. Matches the live template.

### P11 — The cited `path:line` anchors resolve. MOSTLY HOLDS, three defects
Resolve exactly: `phoenix.hcl:12-17` (ports), `:53` (`:latest`), `:57`
(`vault {}`), `:59-66` (the single env template); `memex.hcl:138-140`,
`:142-143`; `justfile:18-19`; `secrets.tf:15-29`;
`memex_core/server/auth.py:1,52-61`.

Defects:
- **`deployments/applications/services.tf:97-107`** (§4, §7) — the Phoenix
  `nomad_job`/`templatefile` block is at **:104-115**; :97-102 is the
  `null_resource.firewall` provisioner. Cited twice.
- **`phoenix.hcl:6-9`** (§4) cited for `network_mode = "host"` — those lines are
  the `orangepi4a` constraint; `network_mode` is `:54`.
- **`apm.yml:2`** (§4, §12) — there is no `apm.yml` at the repo root. It exists
  only at `apm_modules/JasperHG90/memex/apm.yml:2` (`version: 2a053a7`, correct),
  a path that is gitignored (`.gitignore:22`) and **absent from the ticket
  worktree**, so an implementer cannot open it.

### P12 — Gate claims. HOLDS
`justfile:18-19` is `pre_commit: pre-commit run --all-files`;
`.pre-commit-config.yaml:1` is `exclude: '^\.(claude|loop)/'`; the hooks include
`nomad fmt -recursive` (:18), `terraform fmt -check -recursive` (:24), and
`scripts/tf_validate.sh` (:30), which exists.

### P13 — No other ticket declares R4 as a dependency. HOLDS
Every `dependencies` array in `.loop/ledger.json` checked; none names R4.

### P14 — The evals detect the UI gate. BREAKS
No `ls`/`grep`/file-existence scorer appears in
`.loop/evals/R4-rollout-phoenix-oauth2-proxy.md`; every row is a curl, a
`nomad job status`, or the rubric row. The defect is worse than a shape check:
two rows produce a **false negative against a correct implementation**.

- Row `.loop/evals/…:29` expects `curl -sI https://phoenix.lab.orangecluster.nl/`
  to return `302`/`307`/`401` and explicitly fails `200` with the Phoenix HTML
  console. Phoenix is an SPA: with auth enabled, `GET /` falls through to
  `index.html` with HTTP 200 and the gate is applied client-side plus on the
  API/GraphQL layer (`src/phoenix/server/app.py:290-340`, `Static.get_response`
  404-fallback rendering `index.html` with an `authentication_enabled` context
  flag). There is no server-side redirect for `/`. The only server-side 302 in
  that path is `/login` when `PHOENIX_DISABLE_BASIC_AUTH` **and** auto-login are
  both set (`app.py:311-323`).
- Row `:30` then follows `curl -L` from `/` and requires the chain to reach
  Vault's authorize endpoint. `curl -L` cannot follow a client-side redirect, so
  this row can never pass as written.

Both are labelled load-bearing. An implementer chasing them is pushed back
toward putting something in front of Phoenix that *does* emit a 302 — the exact
design this rewrite removed.

### P15 — The redirect URI Phoenix builds behind the TLS-terminating edge is https. UNCERTAIN
Phoenix derives the origin from the `Referer` header when present, else from
`request.base_url` (`oauth2.py:104-113`). HAProxy terminates TLS and proxies
plain HTTP to `192.168.2.29:6006` (`haproxy.hcl:144`) and sets **no**
`X-Forwarded-Proto` and no `option forwardfor` (`defaults` block,
`haproxy.hcl:76-86`). The browser referer path should yield https, but the
fallback yields `http://…/oauth2/vault/tokens`, which Vault will reject against
an https-registered redirect URI. Worth one explicit check, since T3 created
this condition after the design was first drafted.

## Most dangerous assumption

**P5/P6 — that a client plus three env vars completes the login.** Phoenix
unconditionally requires an `email` claim; Vault emits none and silently drops
the `email` and `profile` scopes rather than complaining. Implemented as
written, R4 applies cleanly, the console redirects to Vault, the Vault login
succeeds, and the callback dies with `missing_email_scope` — with no step in
§10 and no deliverable in F2 that would have produced the missing claim.

## Required fixes before this plan can leave PLANNING

1. Add the email-claim requirement to §4/§6/§7/§10: a Vault
   `vault_identity_oidc_scope` named `email` with a template emitting the claim,
   that scope in the provider's `scopes_supported`, and an identity entity that
   carries the value. State whether R4 or F2 owns it, and feed the requirement
   back to F2 (`F2 …:114-116` currently promises a group-claim scope only, and
   `:95-96` leaves entity wiring unresolved). Record `PHOENIX_OAUTH2_VAULT_EMAIL_ATTRIBUTE_PATH`
   (`config.py:2254-2332`) as the fallback lever if the claim lands under a
   different key. Evidence: `config.py:1523`, `oauth2.py:439-450`,
   `identity_store_oidc_provider.go:1751-1757`, live discovery
   `scopes_supported: ["openid"]`.
2. Correct the redirect URI in §7 to
   `https://phoenix.lab.orangecluster.nl/oauth2/vault/tokens`
   (`oauth2.py:79-81,145`), and add updating the F2 key/provider
   `allowed_client_ids` to the code surface (`F2 …:145-154`).
3. Rewrite eval rows `:29` and `:30`. Gate detection must target something
   server-side: `GET /oauth2/vault/login` returning a 302 whose `Location` is
   Vault's authorize endpoint with the Phoenix `client_id`, plus an
   unauthenticated REST/GraphQL call returning `401`. Keep an explicit assertion
   that `GET /` returning 200 SPA HTML is expected, so nobody "fixes" it by
   reintroducing a proxy. Evidence: `app.py:290-340`.
4. Fix the stale HAProxy claims: §4 "MLflow and Bifrost use the same line" and
   §5's Bifrost non-goal (B1/`ac3267b` removed Bifrost's line on 2026-07-29;
   only `haproxy.hcl:143` and `:153` remain), and §12's memex claim (`backend
   memex`, `haproxy.hcl:146-147`, has no auth line and never had one — memex's
   edge is open, which changes the shape of the ticket §12 proposes).
5. Repair the three anchors: `services.tf:97-107` to `:104-115` (both
   occurrences), `phoenix.hcl:6-9` to `:54` for `network_mode`, and `apm.yml:2`
   to `apm_modules/JasperHG90/memex/apm.yml:2` with a note that the path is
   gitignored (`.gitignore:22`) and absent from the ticket worktree.
6. Add the reverse-proxy scheme check to §10 step 5 (P15): HAProxy sets no
   `X-Forwarded-Proto` (`haproxy.hcl:76-86`), so confirm the redirect URI Phoenix
   builds is https on the fallback path, and decide on
   `PHOENIX_CSRF_TRUSTED_ORIGINS`, which the docs recommend when configuring
   OAuth2 clients and which §7's env list omits.

## Attack surfaces, reported explicitly

1. **Stale premise** — found: P8 (Bifrost's basic auth, removed 2026-07-29,
   three days after the rewrite). Also P2's weaker form: the capability list in
   §4 is drawn from docs describing a newer Phoenix than the deployed 13.19.2.
2. **Inlined conclusion** — no instance found. R4's claims about F2 are
   attributed to F2's plan and check out against it; Q1 is backed by a source
   read I reproduced; no unrun ticket's conclusion is asserted as settled.
3. **Broken dependency edge** — found: P6 (F2 delivers a group-claim scope and
   conditional entity wiring; R4 needs an email claim).
4. **Shape-check eval** — no `ls`/`grep`/file-existence scorer. Found instead
   two deterministic rows that fail a correct implementation (P14).
5. **Unresolvable anchor** — found: three (P11).

## Contract hygiene (assessed, subordinate to the premise)

Non-goals are explicit (§5). Forks live in Open Questions with recommendations,
and the superseded 2026-07-23 resolutions are tracked rather than quietly
dropped (§11) — Q4's flag that ingest auth is a genuine change to what the
operator approved is the right call. Gates are discovered, not assumed, and
verified correct (P12). §13's rename recommendation is honest and its ledger
claim checks out (P13). The plan's own risk section names the `:latest` and
silent-ingest-loss hazards accurately. This is a well-made plan whose remaining
defects are substantive rather than cosmetic.
