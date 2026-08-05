---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider"]
priority = 12
summary = "Point Grafana's built-in generic OAuth client at Vault's OIDC provider, so Grafana joins single sign-on without an oauth2-proxy in front of it. Configuration only; Grafana already authenticates, so this improves the login rather than closing a hole."
tags = ["grafana", "oidc", "vault", "terraform"]
---

# Ticket: G1-grafana-native-oidc-login

## 1. Title
Point Grafana's built-in generic OAuth client at Vault's OIDC provider, so
Grafana joins the single sign-on story without an oauth2-proxy in front of it.

## 2. Size / Effort
**Small.** Configuration only: a handful of `GF_AUTH_GENERIC_OAUTH_*` settings
and an OIDC client in Terraform. No new job, no proxy, no HAProxy change. The
effort is in the lockout question (Q1) and role mapping (Q2), not the wiring.

## 3. Triggered by
Operator, 2026-07-26. Every other human-facing service in the rollout epic is
planned behind oauth2-proxy, and Grafana was assumed to be covered by one of
those tickets. It is not: R1 covers MLflow, R4 Phoenix, R2 NATS, R3 Postgres,
and L1 is the landing page. Grafana was never assigned. It also does not need
a proxy, because it speaks OIDC itself:
https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/generic-oauth/

## 4. Context (measured live 2026-08-04)

Every claim here was re-checked against the running cluster on 2026-08-04.
The earlier draft's "re-read those anchors, line numbers have moved" hedges
are replaced with the measured values.

- **Grafana is NOT unauthenticated, and its version is knowable.** Live:
  `curl http://192.168.2.47:3000/` returns `302` to `/login`, and
  `GET /api/health` returns `{"database":"ok","version":"11.5.2"}`. The image
  is pinned at `deployments/infrastructure/services/grafana.hcl:48`
  (`docker.io/grafana/grafana:11.5.2`), so unlike R4's Phoenix this ticket
  can state the deployed feature set from the repo. This ticket improves the
  login rather than closing a hole.
- Auth today is a local admin account. `GF_SECURITY_ADMIN_USER = "admin"` is
  set in the plain env block at `grafana.hcl:67-75`; the password is a
  Terraform `random_password` (`secrets.tf:47-50`) written to KV2 at
  `default/grafana/admin` (`secrets.tf:52-66`) and injected by the
  Vault-templated block at `grafana.hcl:77-84`. The job is rendered from
  `services.tf:346-368`.
- **There are two places to put a setting, and the choice is not cosmetic.**
  Non-secret values go in the plain `env` block (`grafana.hcl:67-75`);
  anything read from Vault goes in the `template { env = true }` block
  (`grafana.hcl:77-84`), which already exists alongside a `vault {}` stanza
  at `grafana.hcl:29`. No new mechanism is required.
- **`GF_SERVER_ROOT_URL` is currently wrong for OIDC.** `grafana.hcl:70` is
  `http://192.168.2.47:3000` — a plain-HTTP node address. Grafana builds its
  redirect URI from `root_url`, so leaving this alone means Grafana sends a
  redirect URI that neither matches what Vault has registered nor works
  through the TLS edge. Changing it to
  `https://grafana.lab.orangecluster.nl` is load-bearing, not tidying.
- **Vault's OIDC provider exists; F2 is `done`.** The issuer is
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`
  (`deployments/infrastructure/oidc.tf:95-101`). Point at the `lab` provider,
  never Vault's built-in `default`, whose `allowed_client_ids` is `["*"]` and
  whose issuer is a raw-IP `http://` URL.
- **F2 shipped no Grafana client. G1 registers its own.**
  `local.oidc_provider_client_ids` (`oidc.tf:80-84`) names smoke, nomad and
  memex. The written procedure is `docs/vault-human-auth.md:264-300`: a
  client with real `redirect_uris`, an assignment (or the built-in
  `allow_all`), a `vault_identity_oidc_key_allowed_client_id` registering it
  against the `lab` key, and one appended line in
  `local.oidc_provider_client_ids`. **Omit that last line and Vault refuses
  the authorization request.** The worked example to copy is the smoke client
  at `oidc.tf:134-149`, or `nomad_oidc.tf:44-57` — both confidential clients on
  the shared `lab` key, which is what Grafana needs. **Not `memex_oidc.tf`**:
  it is a public client on its own key, and §7 explains why copying it is
  expensive to undo.
- **What the live issuer actually offers, fetched 2026-08-04** from
  `…/provider/lab/.well-known/openid-configuration`:

      authorization_endpoint  https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize
      token_endpoint          …/v1/identity/oidc/provider/lab/token
      userinfo_endpoint       …/v1/identity/oidc/provider/lab/userinfo
      scopes_supported        ["groups", "openid"]
      claims_supported        []
      response_types_supported ["code"]
      code_challenge_methods_supported ["plain", "S256"]

  Two things in that document shape this ticket and are covered in the next
  section: **there is no `email` scope and no `profile` scope**, and the
  authorization endpoint is a **UI** path rather than an API one.

### The claim Grafana needs, and what Vault will not give it

Grafana identifies a user from the ID token or the userinfo response. Its
generic OAuth client resolves a login and an email through
`login_attribute_path` and `email_attribute_path`, and it will refuse to
create a session when neither resolves.

Vault's `lab` provider advertises `scopes_supported: ["groups","openid"]` and
`claims_supported: []`. There is no email and no preferred_username. Worse,
**Vault does not error on a scope it does not advertise — it silently drops
it.** This repo's own documentation records the behavior:
`docs/vault-human-auth.md:447-449` — Vault "ignores an unsupported scope
rather than [erroring]", leaving a valid, signed token carrying no claim.

So a client plus three env vars is not enough, and the failure is invisible
until the callback. There are two ways out and the ticket must pick one
explicitly rather than discover it during implementation. See Q4.

The same defect was found in R4 (Phoenix) by its plan review. G1 and R4 should
resolve it the same way, and whichever lands first should own the shared part.

## 5. Non-goals / out of scope
- **Putting Grafana behind oauth2-proxy.** It has a native OIDC client; a
  proxy in front would be a second, redundant auth layer.
- Creating the Vault OIDC provider, issuer, or signing keys. That is F2, and
  it is `done`. Registering G1's own client against that provider is in
  scope — F2 shipped the issuer, not a client per consumer.
- Bumping Grafana off `11.5.2`. The pin stays.
- Changing Grafana's network reachability. N1 deliberately leaves its firewall
  rule alone.
- Migrating dashboards, datasources, or alert rules.
- Removing Grafana's local admin account. See Q1: that is the lockout
  question, and this ticket should not silently answer it.
- Anonymous or viewer-without-login access.

## 6. Requirements & restrictions
1. Grafana authenticates users against Vault's OIDC provider using its own
   generic OAuth client. No proxy.
2. The client ID and secret come from Vault KV2 via the existing
   `template { env = true }` pattern, never hardcoded (`CLAUDE.md` Secrets
   convention). `detect-private-key` (`.pre-commit-config.yaml:12`) stays
   green.
3. The OIDC client is declared in Terraform, never created by hand in Vault,
   and it follows the four-step consumer procedure at
   `docs/vault-human-auth.md:264-300`: the client with its real
   `redirect_uris`; the assignment (or `assignments = ["allow_all"]` for flat
   access, which skips the assignment resource); the
   `vault_identity_oidc_key_allowed_client_id` against the `lab` key; and the
   appended entry in `local.oidc_provider_client_ids` (`oidc.tf:80-84`).
   The last one has no standalone resource and is the easiest to forget;
   without it Vault refuses the authorization request.
4. **`GF_SERVER_ROOT_URL` changes and the redirect URI must agree with it.**
   Both use `https://grafana.lab.orangecluster.nl`. `grafana.hcl:70` is
   currently `http://192.168.2.47:3000`, and Grafana derives the redirect URI
   it sends from `root_url`, so leaving it produces a redirect URI Vault has
   not registered. The failure presents as an opaque provider-side error, not
   a Grafana one.
5. **The token must carry an `email` claim.** Not "some usable identity" —
   specifically an email. Grafana 11.5.2 refuses a login whose resolved email
   is empty and offers no setting to disable that check, so Q4 route (b) is
   the only way this ticket works: the `email` scope, its entry in the
   provider's `scopes_supported`, and the entity metadata behind it. Verify by
   decoding the issued token, not by the redirect appearing to work.
5a. **Set `GF_AUTH_GENERIC_OAUTH_SCOPES` explicitly, and include `openid`.**
   Grafana's default is `user:email` with no `openid` (`conf/defaults.ini`
   line 847 at the deployed tag). Vault does **not** silently ignore that:
   its authorize handler hard-rejects a request whose scope parameter omits
   `openid` (`identity_store_oidc_provider.go` line 1748, "scope parameter
   must contain the \"openid\" value"). So the default configuration cannot
   reach the token endpoint at all, and the first click fails opaquely. This
   is the opposite of the silent-drop behavior documented for *unsupported*
   scopes — a missing `openid` is a loud rejection, an unsupported extra is a
   quiet omission. Request `openid email`.
5b. **Spell out `auth_url`, `token_url` and `api_url`.** Grafana 11.5.2's
   generic OAuth client has **no OIDC discovery** — it will not read the
   well-known document, so pointing it at an issuer URL is not enough. Take
   the three values from the live discovery output quoted in §4. Mind the
   `api_url` trap in Q4: it is the userinfo endpoint, and setting it wrong
   sends Grafana to `<api_url>/emails`.
6. Preserve a way in that does not depend on Vault (Q1). Vault being sealed or
   the OIDC provider misconfigured must not mean nobody can reach the
   dashboards that would diagnose it.
7. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
8. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## 7. Code surface
- `deployments/infrastructure/services/grafana.hcl:67-75` — the plain `env`
  block. Change `GF_SERVER_ROOT_URL` (`:70`) to
  `https://grafana.lab.orangecluster.nl` and add the non-secret
  `GF_AUTH_GENERIC_OAUTH_*` settings here.
- `deployments/infrastructure/services/grafana.hcl:77-84` — the
  Vault-templated `template { env = true }` block. The client **secret** goes
  here and only here, read from KV2 the way
  `GF_SECURITY_ADMIN_PASSWORD` already is. The `vault {}` stanza it needs is
  already present at `grafana.hcl:29`.
- `deployments/infrastructure/oidc.tf` — the client, its key registration,
  and the `local.oidc_provider_client_ids` entry, per requirement 3.
  **The redirect URI is `https://grafana.lab.orangecluster.nl/login/generic_oauth`.**
  Write it exactly: Grafana derives it from `root_url` plus that fixed path,
  requirement 4 turns on it, and §8 row 3 asserts it.
  **Copy `deployments/infrastructure/oidc.tf:134-149` (the smoke client) or
  `nomad_oidc.tf:44-57`, not `memex_oidc.tf`.** Both of those are
  `client_type = "confidential"` registered against the shared `lab` key,
  which is what Grafana needs. memex is a **public** client on its own
  `memex_human` key, and `memex_oidc.tf:55` records that `client_type` and
  `key` are both immutable after create — so copying it costs a destroy and
  recreate, a new `client_id`, and a matching edit everywhere the old one was
  named.
- `deployments/infrastructure/secrets.tf:47-66` — store the client secret in
  KV2 following the `random_password` + `vault_kv_secret_v2` shape used for
  the Grafana admin password. Note the hazard recorded at
  `docs/vault-human-auth.md:308-312`: `detect-private-key` will **not** catch
  a leaked Vault client secret, because it matches a fixed list of PEM
  headers and `hvo_secret_...` is not one. The hook staying green is not
  evidence the secret stayed out of the repo.
- `deployments/infrastructure/services.tf:346-368` — thread the new secret
  path into the grafana `templatefile(...)` var map, beside the existing
  `grafana_secret` var.
- **`deployments/infrastructure/services.tf:364` — a second copy of the wrong
  URL, with a different job.** `grafana_external_url = "http://192.168.2.47:3000"`
  is a separate hardcoded value from `grafana.hcl:70`. Be precise about what
  it does, because an earlier draft of this plan got it wrong: its **only**
  consumer is `grafana.hcl:300`, the "Open Grafana" link in the Telegram alert
  template. It does **not** feed the redirect URI — `GF_SERVER_ROOT_URL`
  (`grafana.hcl:70`) is the single input to that. Change both anyway: leaving
  `grafana_external_url` alone ships Telegram alert messages whose "Open
  Grafana" link points at a bare node address the edge no longer matches. But
  do not describe them as two inputs to one thing.
  Both become `https://grafana.lab.orangecluster.nl`. The edge already routes
  that name: `haproxy.hcl:105` is the ACL, `:116` the `use_backend`,
  `:149-150` the backend to `192.168.2.47:3000`.
- `docs/monitoring.md` — how to sign in, and how to recover if OIDC is down.

## 8. Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` (`justfile:18`), all Passed. Of the fourteen
  hooks in `.pre-commit-config.yaml`, the ones that bite here are
  `nomad-fmt` (`:16`, typed to `.hcl`), `terraform-fmt` (`:22`) and
  `terraform-validate` (`:28`, `scripts/tf_validate.sh`). The four `cli/`
  hooks are scoped away. `.pre-commit-config.yaml:1` excludes
  `^\.(claude|loop)/`, so this ticket file is not linted.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:44`),
  which seeds the gitignored `vars/prod.tfvars`.
- **Command:** `terraform -chdir=deployments/infrastructure plan` adds the
  OIDC client and the secret and updates the grafana job in place. Destroys
  nothing.

### Evals — the authoritative set is `.loop/evals/G1-grafana-native-oidc-login.md`
(author with `create-eval` before implementation; `require_eval` is on and the
marker does not exist yet). The marker MUST carry at least these seven rows:

1. **A real browser login, end to end.** The rubric row. Expect the
   Vault-UI-session quirk in subticket 5 as a known first-attempt behavior.
2. **The email claim actually reached Grafana.** This is the row that catches
   a mis-authored scope, and without it every other row can pass while the
   login is broken. It has been written three times with an unrunnable method,
   so the method matters as much as the assertion.
   **Assert the RESOLVED email, not the raw claim.** After completing the SSO
   login, `GET /api/org/users` with the local admin's basic auth — the same
   request row 7 makes — and confirm the SSO user's `email` field
   (the `Email` field on Grafana's `org.OrgUserDTO`) is present and non-empty. A blank or
   synthesized email there means the claim never arrived, whatever the Vault
   side looks like. One request covers this row and row 7.
   **Optionally, to see the raw claim**, run a code flow against **G1's own
   client**, whose redirect URI this ticket controls, requesting
   `scope=openid email`, then `base64 -d` the `id_token`'s payload segment, or
   call the `lab` provider's `userinfo` endpoint,
   `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/userinfo`
   with the access token from that flow.
   **Two routes that look obvious and do not work.** The `oidc-smoke` client
   is not a shortcut: its redirect URI is a fixed Vault UI callback
   (`variables.tf:64-68`), not operator-controlled, and it is confidential, so
   the exchange needs its secret. And you **cannot read the `id_token` Grafana
   received**: Vault advertises `response_types_supported: ["code"]`, so
   Grafana exchanges the code server-side and the browser never sees a token;
   it is persisted encrypted, so recovering it means exec'ing into the Podman
   task, querying sqlite under the volume mount, and decrypting with Grafana's
   secret key; and no OSS API returns it. The only browser-visible path is
   `id_token_hint` on signout, which is gated on `signout_redirect_url` —
   empty by default and not set by this ticket.
3. **One cheap read-only probe of the whole client configuration.**
   `GET /login/generic_oauth` with no `code` parameter 302s to the provider
   (`pkg/api/login_oauth.go` lines 31-48), and the `Location` header carries
   `auth_url`, `client_id`, the derived `redirect_uri` **and** the `scope`
   parameter. One request checks four settings at once, including that
   `scope` contains `openid` and that `redirect_uri` is the
   `lab.orangecluster.nl` hostname rather than the node IP.
4. **The local-admin fallback still works**, per Q1. Sign in that way
   deliberately rather than assuming it survived.
5. **Guardrail: an unauthenticated request is still refused.** Grafana already
   302s `/` to `/login`; this must not regress into anonymous access.
6. **Guardrail: both copies of the root URL changed.** `grafana.hcl:70` and
   `services.tf:364`. They serve different things — the first is the single
   input to the redirect URI, the second only fills the "Open Grafana" link in
   the Telegram alert template (`grafana.hcl:300`) — so missing the second
   does not break login. It ships alert messages pointing at a node address
   the edge no longer matches, which nothing else in this eval would catch.
7. **The SSO-created user has the role Q2 asked for.** Read back the org role
   of the user created through the OIDC login and confirm it is Editor. State
   the method in the marker, as row 2 must: either `GET /api/org/users` using
   the local admin's basic auth (the account Q1 keeps, so this needs no OIDC
   session), or read the role off the user's profile in the UI after signing
   in. Grafana defaults to `auto_assign_org_role = Viewer`, so "we chose
   Editor" without the setting that delivers it produces read-only accounts
   while rows 1 through 6 all pass. The role is re-synced on every login, not
   only at creation, so a wrong setting cannot be masked by an older
   account.

## 9. Risk assessment
- **Lockout is the main risk.** Configured wrong, or with Vault sealed, and
  nobody can log in to the monitoring system precisely when something is
  broken. Requirement 5 and Q1 exist for this. Grafana is where you look when
  the cluster misbehaves, so losing it during an incident is worse than the
  problem it was meant to solve.
- **No usable identity in the token** is the failure this plan nearly missed.
  Vault advertises no `email` and no `profile` scope and drops an unrequested
  one silently, so the redirect works, the Vault login succeeds, and Grafana
  refuses at the callback because it cannot resolve a user. Nothing errors
  until then. See §4 and Q4.
- **Redirect URI mismatch** is the next likeliest configuration error and
  produces an opaque provider-side error. `GF_SERVER_ROOT_URL` is the input
  Grafana derives it from and it is wrong today (`grafana.hcl:70`).
- **The client id is never added to `local.oidc_provider_client_ids`.** Vault
  gates the provider on that list and there is no standalone resource for it,
  so Terraform reports no error and the authorization request is refused.
- **Dependency on F2 is discharged.** F2 is `done` and the `lab` provider
  answers live, so this ticket can be tested end to end today.
- **Blast radius: one service, and it already requires a login.** This is a
  login upgrade, not a hole being closed.
- **Reversibility: high.** Remove the env settings and the local admin login
  works exactly as before.

## 10. Subtickets (ordered)
1. **Confirm the exact setting names for 11.5.2.** The behavioral questions
   this step used to carry are answered — no OIDC discovery, email is
   mandatory, the default scope list omits `openid` (P11) — so what remains is
   mechanical: the precise `GF_AUTH_GENERIC_OAUTH_*` spellings at that
   version, and the `auth_url`/`token_url`/`api_url` values, which come from
   the live discovery output in §4.
2. **Add the `email` scope at the Vault end** (Q4 route (b) — there is no
   alternative). The scope with an **unquoted** placeholder, its entry in
   `oidc.tf:100`'s `scopes_supported`, and the `email` key in
   `vault_identity_entity.operator`'s metadata. Check whether R4 has already
   landed it; if so, consume it rather than creating a second one. Apply, then
   decode an issued token and confirm the claim is present and non-empty.
   Doing this before Grafana is reconfigured means the next step has one
   unknown instead of two.
3. OIDC client, key registration, `local.oidc_provider_client_ids` entry, and
   the client secret into KV2, per requirement 3.
4. Grafana env settings, split correctly between the plain `env` block and the
   Vault template (§7). Includes **both** root-URL changes —
   `grafana.hcl:70` and `services.tf:364` — the explicit
   `auth_url`/`token_url`/`api_url`, and
   `GF_AUTH_GENERIC_OAUTH_SCOPES` containing `openid`.
5. Apply; log in through a browser end to end. Expect a first-attempt quirk
   that is not a bug in this ticket: Vault's authorize endpoint is a **UI**
   path, so a browser holding no Vault UI session can fail the first attempt
   with a generic "Failed to sign in with SSO" and succeed on retry
   (`docs/vault-human-auth.md:324-330`). A genuine authorization refusal
   reads `identity entity not authorized by client assignment` instead.
6. Verify the Q1 fallback actually works, by signing in that way deliberately.
7. Docs.
8. Adversarial review.

## 11. Open questions
- **Q1 — Keep the local admin account, or make OIDC the only way in?**
  *Recommendation:* keep it. Grafana is the tool you reach for when Vault or
  the network is misbehaving, and an OIDC-only configuration means an incident
  in the identity layer also blinds the monitoring. Keeping local login is a
  slightly larger credential surface for a much smaller failure mode. If the
  operator prefers OIDC-only, that decision should be explicit rather than a
  side effect, and the recovery path should be documented before it is needed.
- **Q2 — Map OIDC groups to Grafana roles, or give everyone the same role?**
  *Recommendation:* start flat, with every authenticated user an **Editor**,
  matching the epic's "any successful login is authorized" posture for a
  single-operator home lab. Role mapping is straightforward to add later via
  `role_attribute_path`, and is unnecessary complexity until there is a second
  human with different needs.
  **Naming Editor is not enough — say which setting delivers it.** Grafana's
  default is Viewer, not Editor: with `role_attribute_path` unset the org-role
  mapper falls back to `auto_assign_org_role`, and `conf/defaults.ini` line
  498 ships that as `Viewer`. So doing nothing gives every SSO user a
  read-only account while **every other row in §8 still passes** — the login
  works, the token is right, the redirect is right, and the operator quietly
  cannot edit a dashboard. Row 7 exists solely to catch this. Set the role
  explicitly, either
  `GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH` to a constant `'Editor'` or
  `GF_USERS_AUTO_ASSIGN_ORG_ROLE=Editor`, and add an eval row that reads back
  the role of a user created through SSO (§8 row 7). Decide which of the two
  before implementing; they differ when a later ticket adds real mapping.
  Two consequences of choosing flat, both of which the earlier draft left
  implicit. On the Vault side, flat means `assignments = ["allow_all"]` on the
  client and no `vault_identity_oidc_assignment` at all
  (`docs/vault-human-auth.md:284-289`) — the oauth2-proxy-style "just omit the
  allowlist" is not enough, because the refusal happens at Vault. On the
  Grafana side, flat means G1 does not need the `groups` scope; if a later
  ticket adds role mapping it must **request** `groups` explicitly, since
  Vault emits no claim for a scope the client did not ask for
  (`docs/vault-human-auth.md:300-306`).
- **Q4 — RESOLVED 2026-08-04, and it turned out not to be a fork.** Vault's
  `lab` provider advertises `scopes_supported: ["groups","openid"]` and
  `claims_supported: []` (§4), so the question was how Grafana gets a usable
  identity. Two routes were considered and one is dead:
  - **(a) Point Grafana at what Vault emits, e.g. `login_attribute_path=sub`,
    and accept users with no email. NOT POSSIBLE on 11.5.2.** Grafana rejects
    the login outright when the resolved email is empty —
    `pkg/services/authn/clients/oauth.go` lines 164-166 at the `v11.5.2` tag
    return `required attribute email was not provided`. No setting disables
    it. There is a second trap on the same path: if `api_url` is set, the
    connector reaches `fetchPrivateEmail`, which GETs `<api_url>/emails`
    (`generic_oauth.go` line 520) — a path Vault does not serve — so the
    login dies inside the connector before the email check even runs.
  - **(b) Add an `email` scope at the Vault end. MANDATORY.** A
    `vault_identity_oidc_scope` named `email`, added to the provider's
    `scopes_supported` (`oidc.tf:100`), plus an `email` key in
    `vault_identity_entity.operator`'s metadata (`auth_userpass.tf:38-44`).
  **Coordinate with R4.** R4 (Phoenix) hit the identical wall and also
  hard-requires an email. Doing (b) once serves both; whichever of G1 and R4
  lands first owns the shared resources and the second consumes them. They
  must not both create the scope. There is no self-contained variant of this
  ticket to fall back on.
  If (b) is chosen, the scope template is
  `{"email":{{identity.entity.metadata.email}}}` — **unquoted**, the same rule
  as the `groups` scope beside it. `oidc.tf:59-69`'s rule is general, not
  list-specific: Vault's identity templating emits fully-formed JSON per
  substitution, and a metadata lookup arrives already quoted. Adding quotes
  yields `{"email":""a@b.com""}`, which Vault rejects at `terraform apply`
  because scope creation validates the template against a zero-value entity.
  The error is real; do not "fix" it by adding quotes.
- **Q3 — Does `auto_login` or `oauth_auto_login` get enabled?** It skips the
  Grafana login page and jumps straight to Vault. *Recommendation:* leave it
  off initially. With it on, a broken OIDC configuration can make the login
  page itself unreachable, which interacts badly with Q1's fallback. It also
  interacts with the UI-path quirk in subticket 5: jumping straight to a Vault
  UI URL from a browser with no Vault session is exactly the case that fails
  opaquely.

## Premises / assumptions

- **P1.** Grafana already requires a login, so this ticket improves the login
  rather than closing a hole. `probe:` `curl` against
  `http://192.168.2.47:3000/` returns `302` to `/login`. Probed 2026-08-04.

- **P2.** The deployed Grafana is 11.5.2 and the version is knowable from the
  repo, so capability claims can be pinned rather than hedged.
  `Evidence:` `deployments/infrastructure/services/grafana.hcl:48` pins
  `docker.io/grafana/grafana:11.5.2`. `probe:` `GET /api/health` returns
  `{"database":"ok","version":"11.5.2"}`. Probed 2026-08-04.

- **P3.** The job already carries everything this change needs mechanically.
  `Evidence:` `grafana.hcl:29` is `vault {}`; `:67-75` is the plain `env`
  block; `:77-84` is the Vault-templated `template { env = true }` block that
  injects `GF_SECURITY_ADMIN_PASSWORD`.

- **P4.** `GF_SERVER_ROOT_URL` is a node-IP HTTP address today and must
  change. `Evidence:` `grafana.hcl:70` is
  `GF_SERVER_ROOT_URL = "http://192.168.2.47:3000"`.

- **P5.** The secret-provisioning pattern to copy resolves.
  `Evidence:` `deployments/infrastructure/secrets.tf:47-50` is
  `random_password.grafana_admin`; `:52-66` writes it to KV2 at
  `default/grafana/admin`. The job is rendered from `services.tf:346-368`.

- **P6.** Vault's `lab` OIDC provider exists, is HTTPS, and F2 is `done`.
  `Evidence:` `deployments/infrastructure/oidc.tf:95-101` sets
  `https_enabled = true`. `probe:` fetching
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration`
  returns a valid discovery document. Probed 2026-08-04.

- **P7.** That provider offers no email and no profile scope, and no claims.
  `probe:` the same discovery document returns
  `"scopes_supported":["groups","openid"]` and `"claims_supported":[]`.
  Probed 2026-08-04. This is the premise Q4 exists to answer.

- **P8.** Vault drops an unadvertised or unrequested scope silently rather
  than erroring, so the consequence of the previous premise is invisible
  until the callback. `Evidence:` `docs/vault-human-auth.md:447-449` and
  `:300-306` both record the behavior for `groups`.

- **P9.** Vault's authorization endpoint is a UI path, which shapes both the
  login experience and any eval that probes it. `probe:` the discovery
  document returns `"authorization_endpoint":
  "https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize"`.
  Corroborated by `docs/vault-human-auth.md:324-330`, which records the
  first-attempt failure when the browser holds no Vault UI session.

- **P10.** F2 shipped no Grafana client, so G1 registers its own, and the
  procedure is written down. `Evidence:`
  `deployments/infrastructure/oidc.tf:80-84` lists three client ids — smoke,
  nomad, memex. The four-step procedure is `docs/vault-human-auth.md:264-300`;
  `deployments/infrastructure/oidc.tf:134-149` (the smoke client) is the worked
  example, with `nomad_oidc.tf:44-57` as a second. `memex_oidc.tf:70-92` is
  **not** — it is public and on its own key (see §7).

- **P11. ANSWERED 2026-08-04 by the plan review, against the `v11.5.2` tag.**
  It was UNCERTAIN when this plan was written; three separate questions were
  open and all three now have answers, each of which changed the ticket:
  - **No OIDC discovery.** Grafana 11.5.2's generic OAuth client does not read
    a well-known document. `auth_url`, `token_url` and `api_url` must be given
    explicitly (requirement 5b).
  - **It will not create a user without an email.**
    `pkg/services/authn/clients/oauth.go` lines 164-166 return
    `required attribute email was not provided`, with no setting to disable
    it. This killed Q4 route (a).
  - **Its default scope list omits `openid`.** `conf/defaults.ini` line 847 is
    `scopes = user:email`, and Vault hard-rejects an authorize request whose
    scope parameter lacks `openid` (`identity_store_oidc_provider.go` line
    1748), so the default config never reaches the token endpoint
    (requirement 5a).
  `source:` upstream Grafana and Vault, at the deployed versions 11.5.2 and
  2.0.3. These are not paths in this repo.

- **P13.** Vault quotes a metadata lookup on its way into a JSON scope
  template, so the placeholder is written unquoted — the same rule as the
  `groups` list, not the opposite. `source:` Vault 2.0.3,
  `sdk/helper/identitytpl/templating.go` lines 113-115, where a
  `map[string]string` lookup returns `strconv.Quote(...)`, versus lines
  111-112 for the `[]string` arm. Confirms the general rule stated at
  `oidc.tf:59-69`. An earlier draft of this plan had it backwards.

- **P14.** The edge already serves `grafana.lab.orangecluster.nl`, so this
  ticket adds no routing. `Evidence:` `haproxy.hcl:105` is the ACL, `:116`
  the `use_backend`, `:149-150` the backend to `192.168.2.47:3000`.

- **P15.** The wrong root URL is stored in **two** places, so changing one
  leaves the job half-migrated. `Evidence:`
  `deployments/infrastructure/services/grafana.hcl:70` and
  `deployments/infrastructure/services.tf:364` both hold
  `http://192.168.2.47:3000`.

- **P12.** The repo gate is `just pre_commit` and it does not lint this plan.
  `Evidence:` `justfile:18` defines the recipe;
  `.pre-commit-config.yaml:1` is `exclude: '^\.(claude|loop)/'`.

## Plan review history

### Never reviewed until now

This ticket was advanced to `ready` before the loop's planning-review pass
existed, so its premise had never been attacked. It was blocked on exactly
that basis: every plan reviewed in the 2026-08-01 sweep carried a defect and
several were fatal, and never-reviewed is weaker evidence than reviewed, not
stronger.

### 2026-08-04 — made reviewable

No verdict has been written yet; this section records what changed so the
first reviewer is attacking the current claims rather than stale ones.

- **Restructured** to the numbered contract sections, with a `# Ticket:`
  header and a `Premises / assumptions` block. `loopctl verify-plan`
  previously reported all eleven sections absent.
- **§4 re-measured live** rather than hedged. The earlier text said "re-read
  those anchors; line numbers have moved this week" and left the deployed
  Grafana version unknown. Both are now pinned: 11.5.2, and every anchor
  carries a checked line number.
- **F2's status corrected.** The plan said "Vault's OIDC provider does not
  exist yet". It does, F2 is `done`, and the gap that remains is a Grafana
  client, which G1 now owns explicitly (requirement 3).
- **The identity gap found and raised as Q4.** The live discovery document
  offers no `email` or `profile` scope and no claims, and Vault drops
  unrequested scopes silently. The earlier plan's "a handful of
  `GF_AUTH_GENERIC_OAUTH_*` settings and an OIDC client" would have applied
  cleanly, redirected to Vault, completed the login, and failed at the
  callback. R4 hit the identical wall.
- **`GF_SERVER_ROOT_URL` promoted from a detail to a requirement**, since
  Grafana derives its redirect URI from it and the current value is a
  plain-HTTP node address.
- **P11 left explicitly UNCERTAIN** rather than guessed. The Grafana-side
  capability claims are the ones this plan is least able to support from
  inside the repo, and subticket 1 is ordered first to settle them.

### 2026-08-04, first review — PARTIALLY SOUND, `pass-with-required-fixes`

The approach survived: Grafana speaks OIDC natively, no proxy is needed, and
the Vault-side guidance (including the unquoted claim template, P13) checked
out against the deployed versions. Five required fixes, all applied.

1. **Q4 was not a fork.** Route (a) — point Grafana at `sub` and accept users
   with no email — is impossible on 11.5.2, which rejects an empty email with
   no override. Route (b) is mandatory. Q4, requirement 5 and subtickets 1-2
   were rewritten to stop offering a choice that does not exist.
2. **P11 answered** from the `v11.5.2` tag: no OIDC discovery, so
   `auth_url`/`token_url`/`api_url` must be explicit (new requirement 5b).
3. **The scope defect the plan missed entirely.** Grafana's default scope list
   is `user:email` with no `openid`, and Vault **hard-rejects** an authorize
   request whose scope parameter lacks `openid` — a loud failure, unlike the
   silent drop documented for unsupported scopes. The default configuration
   never reaches the token endpoint. New requirement 5a.
4. **A second copy of the wrong root URL** at `services.tf:364`
   (`grafana_external_url`), added to §7, §10 step 4 and a guardrail eval row.
   Changing only `grafana.hcl:70` leaves the job half-migrated.
5. **§8 now names six required eval rows**, including the token-decode check
   requirement 5 demands and a single read-only probe of
   `GET /login/generic_oauth` that verifies `auth_url`, `client_id`,
   `redirect_uri` and `scope` in one request.

Still open: the eval marker itself does not exist (`require_eval` is on), so
`create-eval` must author it from §8's rows before implementation.

### 2026-08-04, second review — PARTIALLY SOUND, `pass-with-required-fixes`

All five fixes were re-derived from source and hold, including the one this
plan was least sure of: requirement 5a's asymmetry is exact, and both halves
sit ten lines apart in the same Vault 2.0.3 handler — a scope parameter
lacking `openid` is rejected outright, while unsupported extras are filtered
silently against `ScopesSupported`. Route (b) also needs nothing further: no
`email_attribute_path`, `login_attribute_path` or `name_attribute_path`,
because Grafana takes `data.Email` first and falls back to email for login.
And the R4 coordination is safe without a foundation ticket: two tickets both
declaring `vault_identity_oidc_scope "email"` is a duplicate resource address
that `terraform validate` refuses, and that runs as a pre-commit hook — loud,
not silent.

Three defects remained, five fixes, all applied.

1. **Q2 named a role and no mechanism, and this was the most dangerous thing
   in the plan.** "Every authenticated user an Editor" does not happen by
   default: with `role_attribute_path` unset Grafana falls back to
   `auto_assign_org_role`, which ships as `Viewer`. Doing nothing gives every
   SSO user a read-only account while all six eval rows pass. Q2 now names the
   two settings that deliver Editor and §8 gains row 7 to catch it.
2. **A new defect from the previous round's fix 4.** `grafana_external_url`
   (`services.tf:364`) has exactly one consumer, `grafana.hcl:300`, the
   Telegram alert link. It does **not** feed the redirect URI, which has a
   single input. Changing both copies is still right, but §7 and eval row 6
   were teaching a false model of why.
3. **The wrong worked example.** §7 pointed at `memex_oidc.tf`, a public
   client on its own key with both fields immutable. Grafana needs a
   confidential client on the shared `lab` key, so §7 now points at
   `oidc.tf:134-149` or `nomad_oidc.tf:44-57`.
4. **The exact redirect URI was never written down** though requirement 4 and
   eval row 3 both turn on it. It is now stated:
   `https://grafana.lab.orangecluster.nl/login/generic_oauth`.
5. **Eval row 2 named no way to obtain a token** to decode. It now names two.

### 2026-08-04, third review — SOUND, `pass-with-required-fixes`

The premise is now **SOUND**: all fifteen stated premises hold, plus six
implicit ones the reviewer added and verified. Both Q2 options were confirmed
against the `v11.5.2` tag — `role_attribute_path = 'Editor'` is a valid
JMESPath raw string literal that resolves against any input and wins over
`auto_assign_org_role`, and the role is re-synced on every login rather than
only at creation. The redirect URI is right character for character. And one
apparent plan-killer was cleared: `GF_USERS_ALLOW_SIGN_UP = "false"`
(`grafana.hcl:71`) does **not** block OIDC signup, because the OAuth path
consults the per-connector `[auth.generic_oauth] allow_sign_up`, which
defaults to `true`. Recorded so it is not re-litigated.

Five fixes, applied:

1. **A defect the previous round's fix 3 introduced, and the most expensive
   one left.** §7 was repointed away from `memex_oidc.tf` but §4 and P10 still
   ended "`memex_oidc.tf` is the worked example". An implementer reading
   Context first would copy a public client on its own key, and since
   `client_type` and `key` are immutable after create, undoing it costs a
   destroy, a recreate, a new `client_id`, and an edit everywhere it was
   named. All three sites now agree.
2. **§8 row 7 named no method**, the same gap the previous round had to close
   for row 2. It now names two.
3. **Eval row 2 got `oidc-smoke` wrong twice.** Its redirect URI is a fixed
   Vault UI callback (`variables.tf:64-68`), not operator-controlled, and it
   is confidential, so the exchange needs a secret the row never sourced. The
   row now uses Grafana's own login or G1's own client.
4. **Q2 contradicted the row it created**, still claiming "every eval row
   still passes" after row 7 was added to catch exactly that case.
5. **§7 said "alert emails"** two sentences after correctly calling it a
   Telegram template.

Still open, unchanged: the eval marker does not exist, so `create-eval` must
author it from §8's seven rows before implementation.

### 2026-08-04, fourth review — SOUND, `pass-with-required-fixes`

Four of the five fixes were confirmed complete. Fix 1 was swept across all 21
template mentions in the plan — nothing points at `memex_oidc.tf` any more,
both substitutes are confidential clients on the shared `lab` key, and the
repointing did not walk into the `# DO NOT COPY THIS LINE` marker at
`oidc.tf:126`, which sits outside the cited range. Fix 2 holds on both halves:
`GET /api/org/users` does return the role, and basic auth survives OIDC
(`[auth.basic] enabled = true` by default, nothing in the job disables it,
and a live probe returns `401 password-auth.failed` rather than a route
error).

Two fixes applied:

1. **Row 2's method (a) was unrunnable — the third consecutive round this row
   shipped a method that cannot be executed**, and it is the row the plan
   itself calls the one that catches a mis-authored scope. "Read the
   `id_token` Grafana received" is impossible: Vault advertises
   `response_types_supported: ["code"]`, so Grafana exchanges the code
   server-side and the browser never sees a token; the token is persisted
   encrypted, so recovering it means exec'ing into the Podman task, querying
   sqlite under the volume mount and decrypting with Grafana's secret key; and
   no OSS API returns it. The row now asserts the **resolved** email off the
   same `GET /api/org/users` request row 7 already makes, which is one request
   for both rows, and keeps the raw-claim inspection as an optional extra
   against G1's own client. Both dead routes are recorded so a fourth attempt
   does not rediscover them.
2. **§8's lead-in said "six rows" and listed seven.** Row 7 is the one that
   catches the silent Viewer-instead-of-Editor failure, so a lead-in
   licensing six pointed at the row least safe to drop.
