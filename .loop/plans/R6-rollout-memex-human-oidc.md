---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider", "R5-rollout-memex-oidc-auth"]
priority = 5
stub = false
summary = "Humans log into memex with `memex auth login` against the Vault lab provider instead of sharing a static admin key. Bumps the memex server to v1.2.0 (whose client-side credential: id_token setting makes this possible at all), adds a PUBLIC PKCE Vault OIDC client signed by its OWN 30-day key, gates it on two NEW app-user tiers (`app-memex-admins` and `app-memex-readers`), completes the app-user membership extension point in roles.tf, and appends a second element to MEMEX_SERVER__AUTH__OIDC keyed on the id_token's aud = client_id with two grant_rules, the admin tier first. Leaves the break-glass `admin` group alone. Also owns the D1/D2 runbook fix the v1.2.0 log changes force. Static API keys stay."
tags = ["memex", "oidc", "vault", "human-auth", "pkce", "id-token"]
---

# Ticket: R6-rollout-memex-human-oidc

## 1. Title

Give humans SSO into memex through the Vault `lab` OIDC provider: memex
server to v1.2.0, a public PKCE Vault client signed by its OWN 30-day key
and gated on two NEW app-user tiers (`app-memex-admins` and
`app-memex-readers`), and a second provider element on
`MEMEX_SERVER__AUTH__OIDC` verifying the **id_token** with two
`grant_rules`, the admin tier first. Completes the app-user membership
extension point `roles.tf` already promises, and leaves the break-glass
`admin` group untouched. Static API keys stay. R5's workload path is
untouched except for the log-line changes the version bump forces.

## 2. Size / Effort

**M.** Small diff (one new Terraform file with four resources, three edits
to `roles.tf`, one appended list entry, one `local`, one `data` block, one
env line extended, one version string, three docs). Effort drivers:

- Two Terraform roots, applied in order, joined by a cross-root read
  (`data "vault_identity_oidc_client_creds"`). Wrong order fails loud;
  see §9.
- The memex server version bump rides along and must be isolated from
  the config change, or a failure is unattributable (§10 R6c/R6d).
- v1.2.0 INVERTS R5's D2 check. `docs/memex-oidc-verification.md` and
  R5's eval both assert the old polarity and are wrong the moment the
  bump lands (P6).
- The grant proof is a browser login. It cannot be scripted, so §8's V1
  and V5 are operator steps, not commands in a runner.
- `client_type` AND `key` are both immutable after create (P12, P17).
  Getting either wrong means destroy + recreate, a new `client_id`, and a
  matching server `audience` edit.
- A DEDICATED signing key (P17, P18) drags in Vault's 10x rule and its
  key-registration check, which fires at the TOKEN endpoint and so is
  invisible to §8's V3 probe.
- TWO tiers means two `grant_rules` whose ORDER decides what a dual
  member gets (P20). Both tiers need members, and the app-user scaffold
  has nowhere to record them today (P22), so this ticket also completes
  that extension point (R20). That is a SHARED-scaffold edit: adding
  tiers grows F2's smoke assignment by derivation, without a line of
  `oidc.tf` changing (P25).

Every blocking premise from the R5 split is now measured. There is no
probe-first subticket.

## 3. Triggered by

Split out of `R5-rollout-memex-oidc-auth` on 2026-08-03. R5's plan review
(`.loop/archive/R5-rollout-memex-oidc-auth/verdict.plan-validator.md`) proved
the human half impossible as designed: Vault's OIDC provider issues an
**opaque batch token** as `access_token` and signs the JWT into the
`id_token`, while memex v1.1.0 verified only the access token. R5 shipped
the workload half alone and left this ticket a stub.

memex **v1.2.0** (2026-08-04, closing
<https://github.com/JasperHG90/memex/issues/277>) fixed it upstream with
a client-side `credential: "id_token"` setting and names HashiCorp Vault
explicitly (P1). The blocker is gone. This is now a normal rollout.

Operator decisions taken 2026-08-04, before this plan: R5 is applied and
live (P14), the server `memex_version` bump to 1.2.0 belongs to THIS
ticket, the human session is ~30 days on a DEDICATED signing key, and the
gate is TWO tiers rather than one. The last two settle Q2 and Q3; see §11.

Two further decisions taken 2026-08-04, after the plan review, which this
revision carries through §§2 and 4-12:

- **Both tiers are new `local.app_user_groups` entries**,
  `app-memex-admins` and `app-memex-readers`. The break-glass group
  `vault_identity_group.admin` is NOT used and NOT touched (R21, Q2).
- **Q7 is settled: a sibling `local.app_user_group_members` map**, wired
  to `member_entity_ids` on `vault_identity_group.app_user` (R20). That
  completes the extension point `roles.tf:158-161` already promises and
  `docs/cluster-roles.md:140-141` already documents, and every later
  branch-2 consumer inherits it.

The plan review that forced the rest of this revision is
`.loop/verdicts/R6-rollout-memex-human-oidc.plan-validator.md`: §9's
second break-glass lever was wrong (P24 now measures it), §9 understated
the `roles.tf` blast radius while §5 contradicted it (P25 and §9's
expected-diff table now agree), and V5's join/restore trusted a live-state
snapshot (it is a Terraform edit now).

## 4. Context

### Humans share one static admin key today

- The memex admin key is generated by `random_id.memex_admin_key`
  (`deployments/applications/secrets.tf:71`) and written to Vault KV by
  `vault_kv_secret_v2.memex_auth_keys`
  (`deployments/applications/secrets.tf:79-86`).
- The operator's own memex client reads it from a `MEMEX_API_KEY` line in
  the gitignored `.devcontainer/.env` (gitignored at `.gitignore:2`;
  `.devcontainer/.env.example` never listed it, so it was added by hand).
  That is the credential this ticket replaces.
- Server-side the key path is `MEMEX_SERVER__AUTH__KEYS`
  (`deployments/applications/services/memex.hcl:140`), inside a
  `{{- with secret ... }}` / `{{- end }}` pair (`:139`, `:141`).

### What R5 already landed, and what this extends

- `MEMEX_SERVER__AUTH__ENABLED=true`
  (`deployments/applications/services/memex.hcl:138`) and a ONE-element
  `MEMEX_SERVER__AUTH__OIDC` array at
  `deployments/applications/services/memex.hcl:148`, with its rationale
  comment at `:142-147`. That element trusts the Nomad issuer,
  `audience: ["memex"]`, one `grant_rule` on `nomad_job_id=hermes`,
  `policy: admin`, no `default_policy`. This ticket appends a second
  element; it changes nothing in the first.
- `local.nomad_oidc_issuer` at
  `deployments/applications/services.tf:24-26`, consumed by
  `nomad_job.memex` (`:167-188`) and `nomad_job.hermes`.
  This ticket adds a sibling `local` for the Vault issuer.
- `memex_version = "1.1.0"` at
  `deployments/applications/services.tf:180`, rendered into
  `ghcr.io/jasperhg90/memex-jetson:${memex_version}` at
  `deployments/applications/services/memex.hcl:38`.
- `docs/memex-oidc-verification.md` is R5's live runbook. S1 asserts
  `1 provider(s).` (`:21-38`), D1 asserts a log line (`:118-138`), D2
  asserts log SILENCE (`:140-160`). The second and third are wrong on
  v1.2.0 (P6); the first is wrong once a second provider lands.
- `.loop/archive/R5-rollout-memex-oidc-auth/eval.md` carries the same three
  assertions at `:15` (S1), `:18` (D2), `:23` (G1, "exactly ONE
  element", "no `vault_identity_oidc_client`"). R5 is `done` and the
  marker is operator-signed (`:26`). See Q4.

### The Vault half this rebuilds

- **F2's consumer contract**, stated in the file:
  `deployments/infrastructure/oidc.tf:72-78` tells a consumer to create
  its own client, assignment and key registration, then append one line
  to `local.oidc_provider_client_ids`
  (`deployments/infrastructure/oidc.tf:79-84`). The shared key is
  `deployments/infrastructure/oidc.tf:42-47`, the `groups` scope
  `:55-70`, the provider `:94-100`, the key-registration pattern
  `:145-148`.
- **The closest precedent is `deployments/infrastructure/nomad_oidc.tf`**
  (G2): assignment on the `developer` group at `:30-34`, client at
  `:44-57`, key registration at `:61-64`. Copy the structure, NOT the
  `client_type` — `:54` is `confidential` because the Nomad server holds
  a secret. A CLI on a laptop cannot, so this client is `public` (P3).
  Do NOT copy its `key` either: `:46` points at
  `vault_identity_oidc_key.lab` by CHOICE, not necessity. `key` is a
  per-client field, and it is the referenced key's `verification_ttl`
  that caps a client's `id_token_ttl` (P17). A dedicated key is what
  buys the 30-day session without touching anyone else.
- **The gate is TWO tiers, and BOTH are new `local.app_user_groups`
  entries** (`deployments/infrastructure/roles.tf:152-163`), named by one
  assignment. That is branch 2 of the four answers at
  `docs/vault-human-auth.md:270-288`, the branch that ships empty and
  exists for exactly this: `app-memex-admins` maps to memex
  `policy: admin`, `app-memex-readers` to `policy: reader`. Bind ONLY
  those two keys (`local.app_user_group_ids["<tier>"]`,
  `roles.tf:192-194`), never `local.all_app_user_group_ids` (`:199-201`),
  per the warning at `docs/vault-human-auth.md:279-281`.
- **`vault_identity_group.admin` is NOT the admin tier**, and that is a
  decision rather than an oversight. That group is break-glass:
  `external_member_entity_ids = true`
  (`deployments/infrastructure/roles.tf:131`) hands membership to a
  `vault write` no apply reverts (`docs/cluster-roles.md:70-73`,
  `:84-94`), the file's own warning says leaving yourself in it is
  invisible to every plan (`deployments/infrastructure/roles.tf:125-126`),
  and it carries Vault's wildcard policy (`:31-116`). Wiring daily memex
  admin to it would mean living in break-glass. Two app-user tiers are
  symmetric, match the scaffold's stated purpose (`:148-151`, "they exist
  to be named by an OIDC assignment so a service can tell its own tiers
  apart"), and leave break-glass alone.
- **The scaffold has no place to record members, and this ticket adds
  one.** `vault_identity_group.app_user`
  (`deployments/infrastructure/roles.tf:165-177`) sets no
  `member_entity_ids`, so a tier created today admits nobody (P22) — even
  though the comment right above it already promises "Adding a person is
  a Terraform edit to member_entity_ids on the resource below, which is
  the point: a tier list should be reviewable" (`:158-161`), and
  `docs/cluster-roles.md:140-141` documents the same edit. R20 closes
  that gap.
- **The `groups` claim is opt-in on the request**, not just the
  template: `docs/vault-human-auth.md:300-306` records that a client
  which does not SEND `scope=openid groups` gets a signed token with no
  `groups` claim and nothing errors. Vault confirms it by ignoring
  unsupported scopes rather than rejecting them (P8).
- `deployments/infrastructure/nomad_oidc.tf:154` already binds
  `bound_audiences = [vault_identity_oidc_client.nomad.client_id]`
  against this same provider, in production. That is the repo's own
  evidence that a Vault id_token's `aud` is the client id; P4 confirms
  it at Vault's source.

### What is missing

memex trusts one issuer (Nomad) and knows nothing about Vault. Humans
have no path off the shared admin key. The app-user scaffold has no place
to record who is in a tier (P22), so branch 2 cannot admit anybody today
and neither memex tier could have a member.

## 5. Non-goals / out of scope

- **DO NOT TOUCH `vault_identity_oidc_key.lab`**
  (`deployments/infrastructure/oidc.tf:42-47`). Its `rotation_period` and
  `verification_ttl` stay at `86400` exactly as they are. That key signs
  for the Nomad UI, Grafana and F2's smoke client, and raising its TTLs
  to buy memex a long session is the tempting shortcut that widens the
  blast radius of every one of them. This ticket adds a SECOND key
  instead. Detector: G4.
- **The workload path.** R5 owns hermes and the Nomad Workload Identity
  JWT. Do not touch `deployments/applications/services/hermes.hcl`, the
  hermes `identity` stanza, either `env_passthrough` list, or the first
  element of `MEMEX_SERVER__AUTH__OIDC`
  (`deployments/applications/services/memex.hcl:148`).
- **No hermes image or wheel bump.** `hermes_version` at
  `deployments/applications/services.tf:131` and the wheel URLs at
  `deployments/applications/services/hermes/Dockerfile:28-30` stay at
  `1.1.0`. The v1.1.0 client is wire-compatible with a v1.2.0 server
  (P7), and rebuilding the agent gateway buys nothing here.
- **Do NOT remove static API keys.** `MEMEX_SERVER__AUTH__KEYS`
  (`deployments/applications/services/memex.hcl:140`) stays for the
  browser extension; `MEMEX_API_KEY` stays in hermes
  (`deployments/applications/services/hermes.hcl:201`, `:437`) and in
  the operator's environment. Without a refresh token the human bearer
  expires and the client falls back to the key (P9), so removing it
  turns an expiry into an outage. Removal is Q5's follow-up.
- **No change to the Vault `lab` provider or scope**
  (`deployments/infrastructure/oidc.tf:55-70`, `:94-100`). The only edit
  to that file is the one-line append at `:79-84`.
- No EDIT to the smoke client (`deployments/infrastructure/oidc.tf:133-148`),
  the smoke assignment (`:123-131`), or
  `deployments/infrastructure/nomad_oidc.tf`. Grafana and the Nomad UI
  already consume the id_token and are unaffected.
  **`vault_identity_oidc_assignment.smoke.group_ids` WILL still grow in
  the plan**, with no line of that file changing: it is
  `concat([vault_identity_group.smoke.id], local.all_app_user_group_ids)`
  (`:129`), and `local.all_app_user_group_ids` (`roles.tf:199-201`) is
  derived from every key in `local.app_user_groups`. Two new tiers means
  two more ids. That is F2's deliberate design (`oidc.tf:125-128`,
  `roles.tf:196-198`, P25), not a defect to correct: §9 lists it as an
  expected diff and §8 G5 checks it.
- **Do not gate memex on `developer` or on `admin`.** `developer` carries
  a real Vault policy
  (`deployments/infrastructure/developer_group.tf:158-164`) and is the
  Nomad/cluster tier; `admin` carries the wildcard policy
  (`deployments/infrastructure/roles.tf:31-116`) and is break-glass.
  Overloading either as a memex label makes a memex grant change a
  cluster-privilege change. memex's tiers are the two new app-user
  entries; see §6 R6.
- **Do not touch `vault_identity_group.admin`
  (`deployments/infrastructure/roles.tf:127-136`).** Not named by the
  assignment, not edited, and no check in §8 writes its membership.
  Detector: G5.
- No change to `docs/workload-identity.md`. The human path mints no
  Nomad audience; `:213` already registers `memex` for R5.
- No device-flow support. Vault advertises no
  `device_authorization_endpoint`, so `memex auth login --device` cannot
  work against it (P2). SETTLED, not open.
- No repo-managed laptop config. The memex CLI on a developer machine is
  outside this repo; the deliverable is the documented snippet in
  `docs/vault-human-auth.md`.
- No `writer` tier. Two tiers only. A third is a follow-up.
- Do not fix the `writer_key_vault_meetings` drift R5 put out of scope.
- No HAProxy, TLS, or DNS change. The redirect target is loopback on the
  operator's own machine.

## 6. Requirements & restrictions

| # | Requirement | Where the repo states it |
|---|---|---|
| R1 | Two OIDC providers on the memex server, selected by `iss`: Nomad (R5's, unchanged) and the Vault `lab` provider | Operator decision; mechanism P1, issuer strings P2 and P5 |
| R2 | The client sends the **id_token**, so the server entry's `audience` is the **client_id**, not `memex` | P1, P4; contrast `deployments/applications/services/memex.hcl:148` |
| R3 | A NEW `vault_identity_oidc_client`, its own assignment, its own key registration, and one appended line to `local.oidc_provider_client_ids` | `deployments/infrastructure/oidc.tf:72-84`; pattern `deployments/infrastructure/nomad_oidc.tf:30-64` |
| R4 | Append to `local.oidc_provider_client_ids`, never replace. Replacing breaks the live Nomad UI login and F2's smoke client | `deployments/infrastructure/oidc.tf:74-78`, `:104-107` |
| R5 | `client_type = "public"` with PKCE. A CLI cannot hold a secret; Vault accepts `none` auth and `S256` | P3; contrast `deployments/infrastructure/nomad_oidc.tf:54` |
| R6 | Gate on TWO NEW `local.app_user_groups` tiers in ONE assignment: `app-memex-admins` (memex `admin`) and `app-memex-readers` (memex `reader`). Bind each tier's own key from `local.app_user_group_ids`, never the all-tiers list | Operator decision 2026-08-04; `docs/vault-human-auth.md:270-288`, `:279-281`; `deployments/infrastructure/roles.tf:148-151`, `:152-163`, `:192-194`, `:199-201` |
| R7 | The client must REQUEST `scope=openid groups`, spelled out, because `scopes` replaces the default list | P1, P8; `docs/vault-human-auth.md:300-306` |
| R8 | Never point at Vault's built-in `default` provider | `deployments/infrastructure/oidc.tf:86-93`, `deployments/infrastructure/nomad_oidc.tf:132-135` |
| R9 | Leave `default_policy` unset on both provider entries, so an unmatched token is refused rather than downgraded | `deployments/applications/services/memex.hcl:142-147`; §8 D2, V4 |
| R10 | Static API keys preserved on server and clients | §5; memex v1.2.0 OIDC how-to line 75 |
| R11 | Nomad HCL `nomad fmt`-clean; Terraform `fmt`-clean and `validate`-clean per root | `.pre-commit-config.yaml:16-21`, `:22-27`, `:28-33`; `scripts/tf_validate.sh:8-20` |
| R12 | Surgical changes only; match surrounding style; no adjacent refactors | `CLAUDE.md` §3 |
| R13 | Plain language in every comment and doc line added | `.claude/rules/plain-language.md` |
| R14 | Docs edited must clear the slop scan | `.claude/rules/slop-scan-for-docs.md` |
| R15 | An adversarial sub-agent review runs before this is reported done | `.claude/rules/adversarial-reviews.md`; `.loop/config.json` `require_review` |
| R16 | Do not silence a failing gate; fix the cause | `.claude/rules/prek-code-quality.md`, `.claude/rules/pre-existing-issues.md` |
| R17 | A DEDICATED `vault_identity_oidc_key` for this client, `rotation_period = 604800` / `verification_ttl = 2592000`, and the client's `key` points at it. `vault_identity_oidc_key.lab` is not edited | P17, P18; §5; contrast `deployments/infrastructure/oidc.tf:42-47` |
| R18 | `id_token_ttl = 2592000` AND `access_token_ttl = 2592000`. The two are coupled, not independent | P21 (Q3); ceiling P17, P18 |
| R19 | The `app-memex-admins` rule comes FIRST in `grant_rules`, so a member of both tiers gets `admin` | P20; §8 V5 |
| R20 | Add `local.app_user_group_members` (tier name to entity-id list) and wire it to `member_entity_ids` on `vault_identity_group.app_user`, so a tier can admit somebody and the tier list stays reviewable in the repo | Operator decision 2026-08-04, Q7; `deployments/infrastructure/roles.tf:158-161`, `:165-177`, `:172-174`; `docs/cluster-roles.md:140-141`; P22 |
| R21 | `vault_identity_group.admin` is not named, not edited, and not written to by any check. It stays break-glass | Operator decision 2026-08-04; `deployments/infrastructure/roles.tf:118-126`, `:125-126`, `:31-116`; `docs/cluster-roles.md:70-73` |

## 7. Code surface

### New file: `deployments/infrastructure/memex_oidc.tf`

Mirror `deployments/infrastructure/nomad_oidc.tf:22-64` (Vault half
only; there is no ACL half here and no aliased provider). FOUR
resources, in dependency order:

- `vault_identity_oidc_key "memex_human"` — **new, and the reason this
  ticket can offer a 30-day session at all**. `name = "memex-human"`,
  `algorithm = "RS256"`, `rotation_period = 604800` (7d),
  `verification_ttl = 2592000` (30d). Vault refuses a
  `verification_ttl` over 10x the `rotation_period` and a
  `rotation_period` under a minute (P18); 30d is 4.3x 7d, so this
  passes. Copy the field shape from
  `deployments/infrastructure/oidc.tf:42-47`, NOT its values, and do not
  edit that resource (§5). Leave `allowed_client_ids` off the resource
  for the cycle reason stated at `deployments/infrastructure/oidc.tf:28-32`.
- `vault_identity_oidc_assignment "memex"` — ONE assignment naming BOTH
  tiers, so both can log in:

  ```hcl
  group_ids = [
    local.app_user_group_ids["app-memex-admins"],
    local.app_user_group_ids["app-memex-readers"],
  ]
  entity_ids = []
  ```

  Two map keys spelled out, never `local.all_app_user_group_ids`
  (`deployments/infrastructure/roles.tf:199-201`), per the warning at
  `docs/vault-human-auth.md:279-281` and the DO-NOT-COPY comment at
  `deployments/infrastructure/oidc.tf:125-128`.
  `vault_identity_group.admin` is NOT named here (R21). Structure
  otherwise as `deployments/infrastructure/nomad_oidc.tf:30-34`:
  referenced directly, no data source.
- `vault_identity_oidc_client "memex"` —
  `key = vault_identity_oidc_key.memex_human.name`,
  `assignments = [vault_identity_oidc_assignment.memex.name]`,
  **`client_type = "public"`** (R5), `id_token_ttl = 2592000`,
  `access_token_ttl = 2592000` (R18),
  `redirect_uris = ["http://127.0.0.1:8250/callback",
  "http://localhost:8250/callback"]`.

  Both `client_type` and `key` are immutable after create (P12, P17), so
  a wrong value costs a destroy + recreate, a new `client_id`, and a
  server `audience` edit. `id_token_ttl` may not exceed the referenced
  key's `verification_ttl` (P17), which is why the key resource above
  must exist first; the Terraform reference gives that ordering for free.

  The port in both URIs is arbitrary and never matched. memex binds an
  ephemeral port (P10) and Vault strips the port from BOTH sides when
  the incoming host is loopback, while comparing scheme, host literal
  and path exactly (P10). memex sends only `127.0.0.1`; the `localhost`
  entry costs nothing and covers a future client that sends it.
- `vault_identity_oidc_key_allowed_client_id "memex"` — pattern at
  `deployments/infrastructure/oidc.tf:145-148` and
  `deployments/infrastructure/nomad_oidc.tf:61-64`, but
  `key_name = vault_identity_oidc_key.memex_human.name`, NOT `lab`.
  Omitting it fails at the TOKEN endpoint with `invalid_client: client
  is not authorized to use the key` (P17), which is after the browser
  redirect and therefore invisible to §8's V3.

### `deployments/infrastructure/roles.tf`

- `:152-163` — add TWO entries to `local.app_user_groups` at the marked
  line (`:154`):

  ```hcl
  "app-memex-admins"  = "Full access to memex through Vault SSO"
  "app-memex-readers" = "Read-only access to memex through Vault SSO"
  ```

  Names follow `app-<service>-<level>` (`docs/cluster-roles.md:107-114`).
  Each name appears in THREE places that must match byte for byte: this
  map key, the `local.app_user_group_ids[...]` lookup in the assignment,
  and the `value` of its `grant_rule` in `memex.hcl`. A wrong lookup key
  fails loudly at plan; a wrong `grant_rule` value fails silently at
  login (§9 mode 11).
- `:152-163` — beside that block, add a sibling `locals` block,
  `app_user_group_members`, mapping tier name to a list of entity ids.
  This is Q7, SETTLED (§11):

  ```hcl
  locals {
    app_user_group_members = {
      "app-memex-readers" = [vault_identity_entity.operator.id]
    }
  }
  ```

  `app-memex-admins` gets no key here and so lands empty; §8 V5 adds it
  as a reviewed Terraform edit. The entity is
  `deployments/infrastructure/auth_userpass.tf:38-44`, the only human
  entity in the cluster (P11). Leave `local.app_user_groups` at the
  name-to-description shape `docs/cluster-roles.md:118-126` documents, so
  every existing consumer instruction stays true.
- `:165-177` — `vault_identity_group.app_user` has **no member field at
  all** today, and the resource writes `member_entity_ids`
  authoritatively (P22), so a tier created now admits nobody and a
  hand-added member is reverted on the next apply. Add one line:

  ```hcl
  member_entity_ids = lookup(local.app_user_group_members, each.key, [])
  ```

  The `[]` default is what lets a tier ship with no members. This
  completes the extension point the comment at `:158-161` already
  promises and `docs/cluster-roles.md:140-141` already documents, and it
  keeps membership reviewable in the repo, which is the property
  `:172-174` protects. Every later branch-2 consumer inherits it.
- `:127-136` — **NOT TOUCHED AND NOT NAMED.**
  `vault_identity_group.admin` stays break-glass (R21). No resource here
  references it and no check in §8 writes its membership.

### `deployments/infrastructure/oidc.tf`

- `:79-84` — APPEND `vault_identity_oidc_client.memex.client_id` to
  `local.oidc_provider_client_ids`. One added line. The file's own
  comment at `:72-78` marks this as the contract. Never replace the
  list (R4). This line also publishes the `memex-human` key on the
  provider's `jwks_uri`, because the provider JWKS is built from the keys
  its allowed clients reference (P19).
- `:42-47` — READ ONLY. See §5.

### `deployments/applications/services.tf`

- `:1-19` (the `data` / `ephemeral` block cluster) — add
  `data "vault_identity_oidc_client_creds" "memex" { name = "memex" }`.
  This is the cross-root channel: the client is created in the
  infrastructure root and read back by static name, with no remote-state
  link. The data source handles a public client and returns an empty
  `client_secret` rather than erroring (P13).
- `:24-26` (`locals`) — add
  `vault_oidc_issuer = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"`,
  beside `nomad_oidc_issuer`. Byte-identical to what Vault advertises
  (P5) and to what the human's client config carries, or provider
  selection by `iss` fails.
- `:167-188` (`nomad_job.memex`) — add two templatefile vars:
  `vault_oidc_issuer = local.vault_oidc_issuer` and
  `memex_oidc_client_id = data.vault_identity_oidc_client_creds.memex.client_id`.
- `:180` — `memex_version` from `"1.1.0"` to `"1.2.0"`. The tag exists in
  the registry (P7).

### `deployments/applications/services/memex.hcl`

- `:148` — extend the JSON array from one element to two. Keep the
  Nomad object FIRST and byte-unchanged; append the Vault object with
  TWO grant rules, **`admin` first**:

  ```
  {"issuer":"${vault_oidc_issuer}","audience":["${memex_oidc_client_id}"],"grant_rules":[{"claim":"groups","value":"app-memex-admins","policy":"admin"},{"claim":"groups","value":"app-memex-readers","policy":"reader"}]}
  ```

  Both `value`s are Vault GROUP NAMES, spelled exactly as the two
  `local.app_user_groups` keys. Order is load-bearing, not cosmetic:
  memex takes the FIRST matching rule and stops (P20), so a person in
  both groups lands on `admin` only because `app-memex-admins` is listed
  first. Swapping them silently downgrades every admin who is also in the
  reader tier, and nothing logs it.

  `audience` is the **client id**, not `memex`: an id_token's `aud`
  carries the client id (P4). That is the one shape difference from
  R5's element. No `default_policy` (R9). Leave `algorithms` at its
  default `["RS256","ES256"]` — both Vault keys are RS256 (P5, P19).
- `:142-147` — extend the comment to cover the second element: which
  issuer, why the audience is a client id, why `app-memex-admins` is
  listed first, and that the group gate is enforced twice (Vault refuses
  to issue at all, memex refuses to authorize). Plain language (R13).
- Quoting is unchanged from R5: `${...}` is Terraform, `$${...}` escapes
  to Nomad (`deployments/applications/services/memex.hcl:7`), `{{ }}` is
  Vault templating. The line needs no `{{ with secret }}` wrapper — the
  client id is not a secret.

### Docs (the declared home for every §8 artifact)

- **`docs/memex-oidc-verification.md`** — the runbook. Three edits and
  one addition:
  - `:21-38` (S1): the expected count moves from `1` to `2`, and the
    "a second provider would mean R6 leaked in" note at `:34-35`
    inverts into "both must be present".
  - `:118-138` (D1): the line still fires but has moved from `info` to
    `warning` (P6). Match on message text, not level word.
  - `:140-160` (D2): **REWRITE, it is inverted.** v1.2.0 logs the
    verified-but-unauthorized case explicitly. Silence is now the
    FAILURE. Replace `:152-155` with the new expected line and delete
    "A silent `403` is the pass here."
  - Add a `## V1..V6` section for the human path (§8), including both
    tier names and the rule-ordering check, and a note that a bearer
    which is not a JWT now logs `not a parseable JWT` (P6), which is the
    one-line diagnosis of a client that forgot `credential: id_token`.
  - Add the guardrails G1-G5 verbatim, G5 included: it is the only place
    the expected smoke-assignment growth is written down for whoever
    reads the next `terraform plan` (P25).
  - Retitle from "Verifying memex workload OIDC" (`:1`) to cover both
    paths.
- **`docs/vault-human-auth.md`** — add memex to the consumer list under
  "Adding a service that logs people in through Vault" (`:262-306`) as
  the first branch-2 consumer, and record four rules every future
  consumer needs: a client that wants a TTL past the shared key's 24h
  brings its OWN `vault_identity_oidc_key` and never edits `lab` (P17,
  P18); Vault matches loopback redirects port-agnostically but the host
  literal and path exactly (P10); a Vault relying party that verifies the
  token itself must read the **id_token** and accept the client id as
  `aud` (P4), the sharper form of the note at `:361-369`; and **how to
  revoke a long-lived id_token, with its real reach** — copy §9's
  break-glass wording verbatim, including what `rotate` does NOT do
  (P24). That paragraph is the one most likely to be believed and acted
  on during an incident, so a wrong claim there is worse than no claim.
  Include the laptop config snippet (Q1).
- **`docs/cluster-roles.md`** — `:140-141` claims "Adding a **person** to
  a tier is an edit to `member_entity_ids`", and today there is nowhere
  to make that edit (P22). R20 creates the place, so extend the "Adding a
  tier" section (`:116-141`) with the `local.app_user_group_members`
  entry beside the `local.app_user_groups` one, and keep `:140-141` as
  the sentence the scaffold now satisfies.
- **`.loop/archive/R5-rollout-memex-oidc-auth/eval.md`** — a supersession note
  only, appended below the sign-off at `:26`. Do not edit the signed
  rows. Q4.

## 8. Tests & validation gates

No unit-test surface: Terraform, Nomad HCL and docs. The repo's Python
gates are scoped `files: '^cli/'` (`.pre-commit-config.yaml:37-53`),
which this ticket does not touch. Verification is the static gates plus
live checks.

### Static gates (must pass)

| Gate | Command | Source |
|---|---|---|
| All hooks | `just pre_commit` | `justfile:18-19`; `.loop/config.json` `gates` |
| Nomad HCL format | hook `nomad-fmt` | `.pre-commit-config.yaml:16-21` |
| Terraform format | hook `terraform-fmt` | `.pre-commit-config.yaml:22-27` |
| Terraform validate, per root | hook `terraform-validate` | `.pre-commit-config.yaml:28-33`; `scripts/tf_validate.sh:8-20` |
| Plan review, infrastructure root | read the plan before `just apply` | `deployments/infrastructure/justfile:11-13` |
| Plan review, applications root | read the plan before `just apply` | `deployments/applications/justfile:13-24` |

Worktree note: `just worktree_setup <path>` (`justfile:44`) seeds the
gitignored SSH key and tfvars that `terraform validate` needs.

### Live checks

Baseline is R5's, re-measured before starting: no credential `401`,
garbage bearer `403`, admin API key `200` (P14).

**S1 — the server loaded exactly two providers.** After the memex
redeploy at R6d:

```
nomad alloc logs <memex-alloc> memex | grep -i 'authentication enabled'
```

Expect `OIDC bearer-token authentication enabled (2 provider(s)).`
alongside `API key authentication enabled (3 key(s) configured, 3 exempt
path(s)).`. `2`, not `1`: a silently dropped provider (bad JSON in the
env var) is the cheapest failure to catch. The INFO level is visible in
this deployment (P14).

**S2 — API-key regression.** Re-run the P14 triple against
`http://192.168.2.46:8000/api/v1/vaults`. Still `401` / `403` / `200`.

**W1 — R5's workload path still works.** From the hermes alloc:

```
nomad alloc exec -task hermes <hermes-alloc> \
  /opt/hermes/.venv/bin/python -c "import asyncio;\
from memex_common.config import MemexConfig;\
from memex_common.auth_client import resolve_client_headers;\
print(asyncio.run(resolve_client_headers(MemexConfig())))"
```

Expect `{'Authorization': 'Bearer eyJ...'}`, then a `200` from
`/api/v1/vaults` with that bearer. This is the regression guard on the
version bump and the second provider element. `resolve_client_headers`
and `_read_workload_token` are byte-identical across the two tags (P7),
so a failure here means the SERVER changed, not the client.

**D1 — DENY, wrong `aud`.** R5's throwaway Nomad job carrying
`identity { name = "vault_default", aud = ["vault.io"], file = true,
filepath = "secrets/nomad_vault_default.jwt" }`; present that token.
Expect `403` and the log line `OIDC token rejected for issuer ...`. On
v1.2.0 that record is `warning`, not `info` (P6). Tear the job down, as
`docs/workload-identity.md:195-198` requires.

**D2 — DENY, non-hermes `nomad_job_id`. POLARITY INVERTED.** From the
same job, present its `aud = ["memex"]` token. Expect `403`, AND expect
the server log to carry:

```
OIDC token verified for issuer ... but matched no grant_rule and the
provider has no default_policy, so it authorizes nothing. Claims present
on the token: [...]
```

Silence here is now a FAILURE, not a pass (P6). This same line is the
detector for the human path's likeliest fault (a token with no `groups`
claim), which is why it is worth having.

**V1 — GRANT, the READER tier.** From the operator's own machine with the
Q1 client config in place, and the operator entity in
`local.app_user_group_members["app-memex-readers"]` but NOT in
`app-memex-admins`. That is exactly the membership R6a lands, so there is
no setup step here; confirm it first with
`vault read identity/group/name/app-memex-admins` reporting no members.

**Precondition, and its failure is silent-ish:** the browser must ALREADY
hold a Vault UI session. Vault's `authorization_endpoint` is the UI path
(`docs/vault-human-auth.md:322-329`), so an unauthenticated browser lands
on the login screen and never redirects back. The CLI does not error — it
waits out its 300 s callback timeout (`memex_cli/auth.py`) and reports a
timeout with nothing pointing at the cause. Log into the Vault UI first,
in the same browser, then run the command.

```
memex auth login      # opens a browser; Authorization Code + PKCE
memex auth status
```

Expect a reported identity and expiry. Then decode the cached id_token
from `<user_config_dir>/memex/token.json` and assert, do not assume:
`iss` equals the value in `local.vault_oidc_issuer`, `aud` equals the
memex client id, and `groups` CONTAINS `app-memex-readers` and does NOT
contain `app-memex-admins` (`_rule_matches` does membership on a list
claim, P1).

Then, with that bearer:

- READ `GET /api/v1/vaults` returns `200`.
- WRITE `PATCH /api/v1/notes/<random-uuid>/title` returns **`403`**. That
  route is guarded by `require_write` (P23), which `reader` does not
  hold, so the gate fires before the handler and the fabricated id
  mutates nothing. Anything other than `403` (a `404`, a `422`) means
  the tier resolved above `reader` and the grant is wrong.

**V2 — DENY, the opaque access token.** From the same `token.json`,
present the `access_token` field (Vault's opaque batch token) as the
bearer instead. Expect `403` and the log line `OIDC bearer rejected: not
a parseable JWT (2 dot-separated segments).` (P6).

**Two, not one.** Vault's batch token is `hvb.` + base64url
(`sdk/helper/consts/token_consts.go`, `vault/token_store.go`), and memex
logs `token.count('.') + 1` (`server/oidc.py`), so a `hvb.<blob>` token
counts 2. Asserting `1` fails a correct system at a 100% bar — the same
defect class this ticket exists to fix in R5's D2. Confirm the count
against the token you actually get rather than trusting either number.

This is the exact failure that made the human path impossible before
v1.2.0, and it is the one-line diagnosis of a client that forgot
`credential: id_token`.

**V3 — the Vault-side gate is live and reached.** No login needed, but
read the token requirement first.

**Use a token with NO identity entity (a root token).** The expected
`access_denied` fires only where `req.EntityID == ""`. With your own
operator token the entity exists AND is in a group the assignment
admits, so both checks pass and Vault returns a `code=` redirect
instead. That is a false alarm — and it also MINTS AN AUTH-CODE ENTRY,
so the probe stops being read-only. `$VAULT_TOKEN` below must be the
root token, not yours.

```
curl -sk -H "X-Vault-Token: $VAULT_TOKEN" -G \
  "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/authorize" \
  --data-urlencode "client_id=<memex client id>" \
  --data-urlencode "redirect_uri=http://127.0.0.1:44444/callback" \
  --data-urlencode "response_type=code" --data-urlencode "scope=openid groups" \
  --data-urlencode "state=abcdefghij" --data-urlencode "nonce=abcdefghij" \
  --data-urlencode "code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM" \
  --data-urlencode "code_challenge_method=S256"
```

Expect `{"error":"access_denied","error_description":"identity entity
must be associated with the request"}`. `access_denied` is the PASS:
Vault checks the redirect URI, the client, the provider's
`allowed_client_ids` and the scope BEFORE the entity, so this one
response proves all four are wired (P10). An `invalid_redirect_uri`
means the loopback registration is wrong; `unauthorized_client` means
the `oidc.tf:79-84` append is missing. Note the arbitrary port `44444`:
that it passes is the port-agnostic match, proved live.

**What V3 does NOT prove, and this matters more now:** the KEY
registration. Vault checks `key.AllowedClientIDs` at the token endpoint,
not at authorize (P17), so a missing
`vault_identity_oidc_key_allowed_client_id` sails through V3 and fails
only at the code exchange in V1. It also does not prove that a member of
some OTHER group is refused; Vault emits a different string for that,
`identity entity not authorized by client assignment`, already recorded
at `docs/vault-human-auth.md:331-334`.

**V4 — DENY, a human token with NO `groups` claim.** This is the check
that exercises §9's likeliest failure mode, and nothing else does: D2
presents a *Nomad workload* token, so no Vault id_token ever travels the
no-matching-grant path.

Run `memex auth login` a SECOND time with `scopes` set to `["openid"]`
only (drop `groups`), then present that id_token to `/api/v1/vaults`.

Expect `403`. Per P8 Vault ignores the unsupported scope rather than
erroring, so login SUCCEEDS and returns a perfectly valid signed token
that simply carries no `groups` claim — which matches NEITHER
`grant_rule`, and with `default_policy` unset authorizes nothing.
Confirm on the log that this is the authorization path, not a signature
failure, using the v1.2.0 message named in P6.

Restore `scopes: ["openid","groups"]` afterwards, so the working config
is what is left in place.

**V5 — GRANT, the ADMIN tier, and the rule ORDER.** This is the only
check that proves R19, and the only one that exercises a dual member.

**No `vault write` here, and no restore step.** Both tiers are ordinary
`vault_identity_group.app_user` instances whose `member_entity_ids`
Terraform owns (R20, P22), so joining is a Terraform edit with a plan you
can read. The break-glass group is not involved (R21): there is no window
in which the operator holds Vault's wildcard policy, and nothing to
restore afterwards.

Add the operator to the second tier in
`deployments/infrastructure/roles.tf`:

```hcl
app_user_group_members = {
  "app-memex-admins"  = [vault_identity_entity.operator.id]
  "app-memex-readers" = [vault_identity_entity.operator.id]
}
```

Apply the infrastructure root and read the plan first: it must show
`vault_identity_group.app_user["app-memex-admins"]` gaining one member
and nothing else. Then re-run `memex auth login` — the old token is
stateless and still says what it said, so a fresh login is required for
the claim to change — and assert:

- the decoded `groups` claim contains BOTH `app-memex-admins` and
  `app-memex-readers`;
- `PATCH /api/v1/notes/<random-uuid>/title` now returns something OTHER
  than `403` (a `404` or `422` from the handler). A `403` here means the
  reader rule matched first and R19 is broken;
- `GET /api/v1/vaults` returns `200`.

**Leave the membership as V5 sets it** unless Q8 says otherwise: both
tiers hold the operator, so every day-to-day login re-exercises the
ordering. Going back to reader-only is the same map edited back and
re-applied, which is a reviewed change like any other.

**Standing rule for any future check that writes `member_entity_ids` on a
group Terraform does NOT manage.** No check in this ticket does — under
R21 the only such group, `vault_identity_group.admin`, is untouched. If
one ever does, the write REPLACES the list rather than merging it
(`docs/cluster-roles.md:70-73`, `:84-94`): read the current set
immediately before writing, restore to exactly that set, never to empty,
and never from a value read earlier in the session. Nothing in Terraform
can diff a mistake there.

**V6 — the session really lasts 30 days.** Cheap, and it catches the one
trap in R18. After the V1 login, read `<user_config_dir>/memex/token.json`
and assert BOTH:

- the cached `expires_at` is roughly 30 days out, not 1 hour;
- the decoded id_token's `exp` is roughly 30 days out.

The memex client caches `min(now + expires_in, id_token exp)`, and
Vault's `expires_in` IS the `access_token_ttl` (P21). If
`access_token_ttl` were left at the repo's usual `3600`, the id_token
would be valid for 30 days while the client threw it away after an hour
and silently fell back to the API key (§9 mode 2). Requests would still
return `200`, so nothing else in this list would catch it.

**G1 (guardrail) — static keys survive.** `MEMEX_SERVER__AUTH__KEYS`
still present in the rendered memex jobspec, `MEMEX_API_KEY` still
present in the rendered hermes jobspec at
`deployments/applications/services/hermes.hcl:201` and `:437`.

**G2 (guardrail) — R5's element is byte-unchanged.** In the rendered
memex jobspec, `MEMEX_SERVER__AUTH__OIDC` holds exactly TWO elements,
and the Nomad one still reads `"issuer":"https://nomad.lab.orangecluster.nl"`,
`"audience":["memex"]`, one `grant_rule` on
`"claim":"nomad_job_id","value":"hermes","policy":"admin"`. The Vault
element holds exactly TWO `grant_rules`, with
`"value":"app-memex-admins","policy":"admin"` at index 0.

**G3 (guardrail) — the provider list was appended, not replaced.**
`terraform plan` on the infrastructure root shows
`vault_identity_oidc_provider.lab.allowed_client_ids` growing from two
entries to three, with the smoke and nomad client ids unchanged. A
shrink or a replacement breaks the live Nomad UI login.

**G4 (guardrail) — the shared `lab` key is untouched.** Two assertions:

- `terraform plan` on the infrastructure root shows NO change to
  `vault_identity_oidc_key.lab`;
- after apply, `vault read identity/oidc/key/lab` still reports
  `rotation_period 86400` and `verification_ttl 86400`, and its
  `allowed_client_ids` still holds exactly the smoke and nomad client
  ids and NOT memex's.

Raising the shared key's TTLs is the shortcut §5 forbids, and it would
extend every Nomad UI and Grafana token by the same amount without
anything else in this list noticing.

**G5 (guardrail) — the scaffold edit landed where it should, and only
there.** Read the infrastructure `terraform plan` at R6a against these
three, and treat anything else in `roles.tf` or `oidc.tf` as a stop:

- exactly TWO new resources under `vault_identity_group.app_user`, keyed
  `app-memex-admins` and `app-memex-readers`, with `member_entity_ids`
  holding the operator on readers and nothing on admins;
- `vault_identity_oidc_assignment.smoke.group_ids` grows from one entry
  to three, and the two new entries are those tier ids. **This diff is
  EXPECTED.** It is derived, not edited: `oidc.tf:129` concats
  `local.all_app_user_group_ids` (`roles.tf:199-201`), which is F2's
  design (`oidc.tf:125-128`, `roles.tf:196-198`, P25). It changes no
  effective access today, because `operator` is the only human entity and
  is already in `oidc-smoke` (P11);
- NO change to `vault_identity_group.admin`, and after apply
  `vault read identity/group/name/admin` still reports no members (P11).
  That is the check that this ticket left break-glass alone (R21).

Every check above is written verbatim into
`docs/memex-oidc-verification.md`.

The scored acceptance layer is the eval marker,
`.loop/evals/R6-rollout-memex-human-oidc.md`: one deterministic row per
check above at a 100% bar. The security-shaped rows (D1, D2, V1's write
denial, V2, V3, V4, V5's ordering, G1, G2, G3, G4 and G5) protect an
invariant, so a row that passes most of the time is a row with a hole.
Nothing enforces the plan-to-eval link; keep them in step by hand.

## 9. Risk assessment

**Blast radius.**

- **A 30-day bearer is the headline risk, and it is deliberate.** Vault
  cannot revoke an id_token once issued: memex verifies it locally
  against the JWKS and never calls back (P1). For 30 days that token is
  a valid memex credential for whoever holds it, and it sits on a laptop
  in `<user_config_dir>/memex/token.json` for that whole time — a plain
  file, not a keyring entry. Losing the laptop means losing a live
  credential with no server-side kill switch on the token itself.
  Compared with the status quo (a shared, never-expiring admin key in a
  `.env`) it is still a net improvement, because it expires at all and
  it names a person. It is not a small credential.
- **The break-glass exists BECAUSE the key is dedicated.** One complete
  lever and one partial one, both memex-only and neither reachable if
  this client shared `lab`:
  1. **Total, one line. THIS IS THE BREAK-GLASS.** Remove
     `vault_identity_oidc_client.memex.client_id` from
     `local.oidc_provider_client_ids`
     (`deployments/infrastructure/oidc.tf:79-84`) and apply. The
     provider's JWKS is built from the keys its allowed clients
     reference (P19), so the `memex-human` key leaves it and EVERY
     outstanding memex human token stops verifying. The Nomad UI,
     Grafana and the smoke client are untouched: they reference `lab`,
     which stays in the list. Reversible by re-appending the line; the
     `client_id` does not change.
  2. **Partial. Know its reach before reaching for it.**
     `vault write identity/oidc/key/memex-human/rotate verification_ttl=0`
     revokes the tokens issued SINCE THE LAST ROTATION, not all
     outstanding tokens. `rotate` stamps `ExpireAt` on the CURRENT
     signing key only and then promotes the next one (P24). Keys rotated
     out at earlier rotations keep the `ExpireAt` they were stamped with
     then, up to 30 days out, and no path revisits them. So calling
     `rotate` repeatedly does NOT converge: call 2 expires a key that was
     just promoted and has signed nothing. With a 7-day rotation inside a
     30-day window, roughly four older ring keys that DID sign live
     tokens stay verifiable and are unreachable this way. The obvious
     escape hatch is shut too: lowering the key's `verification_ttl` does
     not re-stamp existing ring members, and Vault refuses that update
     outright while the client's `id_token_ttl` exceeds the new value
     (P24).

  **Reach for lever 1.** It is the only one that stops every outstanding
  memex human token. Lever 2 is for when you want the client to keep
  working and are content to invalidate the most recent window.

  Either way the effect reaches memex within its JWKS cache TTL of 3600 s
  (P19), or immediately on a memex restart. Neither is instant.
- The `deployments/infrastructure/oidc.tf:79-84` edit touches the shared
  `lab` provider's `allowed_client_ids`. Replacing instead of appending
  takes down the Nomad UI login and F2's smoke client at once. `:104-107`
  warns about exactly this. Detector: G3.
- **The `roles.tf` edit is the widest part of this ticket, and its diff
  reaches a resource in another file.** The scaffold is shared and two
  other tickets are queued against it (M2, F14 follow-ups). Keep the map
  edit additive; a replacement is what breaks other consumers. Then read
  the whole plan against this expected list:

  | Expected diff | Why |
  |---|---|
  | `vault_identity_group.app_user["app-memex-admins"]` created | R6, the admin tier |
  | `vault_identity_group.app_user["app-memex-readers"]` created | R6, the reader tier |
  | `member_entity_ids` appears on both new tiers | R20's new field. Readers gets the operator, admins stays empty until V5 |
  | `vault_identity_oidc_assignment.smoke.group_ids` grows 1 entry to 3 | **DERIVED, not edited.** `oidc.tf:129` concats `local.all_app_user_group_ids` (`roles.tf:199-201`), so every new tier lands in F2's smoke assignment. Deliberate, and both files say so (`oidc.tf:125-128`, `roles.tf:196-198`). No effective access changes today. Full chain and reasoning: P25 |
  | no change to `vault_identity_group.admin` | R21 |
  | no change to `vault_identity_oidc_key.lab` | §5, G4 |

  Detector: G5. An implementer who meets the smoke-assignment growth
  without this table has no way to judge it, and the safe-looking
  reaction — un-derive the list and bind the tiers explicitly — would
  rewrite F2's file over a diff that is working as designed.
- The `memex.hcl` edit plus the version bump redeploy memex, the memory
  backend for hermes and the operator's MCP tooling. A malformed
  `MEMEX_SERVER__AUTH__OIDC` string either fails startup (loud) or loads
  with a provider missing (quiet). S1 is the detector for the quiet case.
- `terraform apply` on either root refreshes every resource in it. Read
  the plan.
- The version bump also re-runs the prestart `database upgrade` task
  (`deployments/applications/services/memex.hcl:39`). The v1.1.0-to-v1.2.0
  compare carries no migration or schema file (P7), so this is a no-op —
  but it is the step that would hurt if that ever stopped being true.

**Reversibility.** Good on config, weaker on the Vault client. The
`local`, the `data` block, the second array element and the version
string all revert cleanly, and the static keys are never removed. The new
key is additive and touches nothing existing. Destroying the Vault client
must be paired with removing its entry from
`local.oidc_provider_client_ids` in the SAME change
(`deployments/infrastructure/oidc.tf:104-107`), or the provider
references a client id that no longer exists. Re-creating it mints a NEW
`client_id`, which invalidates the server's `audience` and every cached
human token. Deleting the key is blocked while the client references it
(P17), so the destroy order is client, then key.

**Likeliest failure modes, in order.**

1. **The `groups` claim never reaches the id_token.** The client did not
   spell out `scope: ["openid","groups"]`, so Vault silently drops the
   scope it was not asked for (P8) and issues a token with no `groups`.
   Login succeeds, then every request is `403`. This is the single most
   likely fault and it is invisible from the response. Detector: D2's
   new log line, which names the claims that WERE present. Proved by V4.
2. **`access_token_ttl` left at `3600` while `id_token_ttl` is 30 days.**
   The client caches `min(now + expires_in, id_exp)` and Vault's
   `expires_in` is the ACCESS token's TTL (P21), so the session dies
   after an hour and falls back to the API key. Requests keep returning
   `200`; only the identity changes. Detector: V6, and nothing else.
3. **The key registration is missing.** Vault checks
   `key.AllowedClientIDs` at the token endpoint, after the browser
   redirect (P17). V3 passes, the browser round-trips, and the exchange
   fails with `invalid_client: client is not authorized to use the key`.
   Reads as a client bug; it is a Terraform omission.
4. **Applications applied before infrastructure.** The `data` source
   fails with `no client found at "identity/oidc/client/memex"` (P13).
   Loud, and fixed by applying in order.
5. **Rule order swapped, `reader` first.** A dual member silently gets
   `reader`. Every read works, writes `403`, and no log line says why —
   memex logs the no-match case (P6) but not a match on a rule you did
   not intend. Detector: V5, and only V5.
6. **A tier admits nobody.** The tier lands with an empty
   `member_entity_ids`, because R20's map has no key for it or the key is
   misspelled and `lookup` returns its `[]` default (P22). Vault refuses
   the authorize with `identity entity not authorized by client
   assignment` (`docs/vault-human-auth.md:331-334`), which is at least
   loud. `app-memex-admins` sits in this state on purpose until V5.
7. **Issuer drift** between `local.vault_oidc_issuer` and the human's
   client config. Provider selection is by exact `iss` match, so a
   trailing slash on one side `403`s every human login with `no
   configured provider matches issuer` (P6) — which, on v1.2.0, names
   the configured issuers in the log.
8. **`client_type` or `key` set wrong by copying
   `deployments/infrastructure/nomad_oidc.tf:46`/`:54`.** Both fields
   are immutable (P12, P17), so the fix is destroy + recreate + a new
   client id + a server `audience` edit. Pointing `key` at `lab` also
   caps `id_token_ttl` at 86400 and Vault rejects the apply outright
   (P17), which is the loud version; `client_type = "confidential"`
   applies clean and fails at login, which is the quiet one.
9. **Expiry at day 30, then a silent downgrade to the API key.** Vault
   issues no refresh token (P2), so at expiry the client warns `Cached
   OIDC token expired and no refresh token is available.` and falls back
   to `X-API-Key` when one is set (P9). Requests keep returning `200`
   while the identity quietly reverts to the shared admin key. Monthly
   rather than hourly now, which makes it easier to miss, not harder.
   Detector: `memex auth status` plus that warning. Q5 is the lever.
10. **The client id shared with a second relying party.** memex applies
    no `azp` check, so any service that can obtain an id_token for this
    client can call memex as that user (P1, v1.2.0 how-to lines 140-144).
    Mitigated by construction: this client is registered for memex only.
11. **A tier name spelled differently in the two places that matter.**
    Each name is a `local.app_user_groups` key, a
    `local.app_user_group_ids[...]` lookup, and a `grant_rule` `value`.
    A wrong lookup key fails LOUDLY at plan (invalid index). A wrong
    `grant_rule` value fails SILENTLY: Vault issues a token carrying the
    real group name, memex matches no rule, and with `default_policy`
    unset the request is refused. It reads exactly like mode 1.
    Detector: D2's log line names the claims that WERE present, so the
    token's actual `groups` value is in the log, and V1 and V5 decode the
    claim and assert it directly.

**One consequence worth stating plainly.** Because both tiers are
Terraform-managed (R20), the operator's day-to-day memex identity through
SSO is whatever `local.app_user_group_members` says, and after V5 that is
`admin`. Reaching memex admin no longer means joining break-glass, which
was the alternative and would have meant holding Vault's wildcard policy
(`deployments/infrastructure/roles.tf:31-116`) every day just to write a
note. The flip side: memex admin is now one reviewed Terraform edit away
rather than gated behind an incident ritual, so the reviewable tier list
IS the control. That is the property `roles.tf:172-174` protects and R20
preserves. Q8 asks where the membership should rest.

## 10. Subtickets

Ordered and dependency-aware. If these become separate plan files,
encode this order in each file's `depends_on`.

1. **R6a — the members map, then both tiers, then the dedicated key.**
   That order inside the subticket: the map and the `member_entity_ids`
   wiring must exist before a tier can carry anybody, and the key must
   exist before R6b's client references it, because `key` is immutable
   after create (P17). Nothing signs or authorizes yet, so this is inert
   and safe to land alone.
   - `deployments/infrastructure/roles.tf`, in order:
     `local.app_user_group_members` and the
     `member_entity_ids = lookup(...)` line on
     `vault_identity_group.app_user` (R20), then the two
     `local.app_user_groups` entries, with the operator in
     `app-memex-readers` ONLY. `app-memex-admins` lands empty on purpose:
     V1 needs a reader-only login to prove the tiers differ, and V5 adds
     the second membership afterwards.
   - `deployments/infrastructure/memex_oidc.tf`: the
     `vault_identity_oidc_key.memex_human` resource ONLY.
   - Apply the infrastructure root, reading the plan against G5's
     expected list first. Read back, read-only:
     `vault read identity/oidc/key/memex-human` reports
     `rotation_period 604800` / `verification_ttl 2592000`;
     `vault read identity/group/name/app-memex-readers` lists the
     operator entity; `vault read identity/group/name/app-memex-admins`
     lists none; `vault read identity/group/name/admin` is unchanged with
     no members. Run G4 and G5.
   - Depends on nothing else. Q7 is settled (§11), so nothing blocks it.
2. **R6b — the client, the assignment and the provider append.**
   - The remaining three resources in
     `deployments/infrastructure/memex_oidc.tf`: the assignment naming
     BOTH `local.app_user_group_ids` keys, the `public` client pointing
     `key` at `memex_human` with both TTLs at `2592000`, and the key
     registration against `memex-human`. The client comes after the key
     and cannot be repointed later (P17).
   - The one-line append at `deployments/infrastructure/oidc.tf:79-84`.
   - Apply. Run G3, G4 and V3. Confirm the provider JWKS at
     `/v1/identity/oidc/provider/lab/.well-known/keys` GREW, which is
     the memex key becoming publishable (P19).
   - Still inert: no server trusts this issuer yet. Depends on R6a,
     because the client cannot reference a key that does not exist and
     `key` is immutable afterwards (P17).
3. **R6c — memex server to v1.2.0, still ONE provider.**
   `deployments/applications/services.tf:180` to `"1.2.0"`, then
   `just apply true nomad_job.memex` from
   `deployments/applications`. Run S1 (still `1 provider(s).`), S2, W1,
   D1, D2. **Rewrite `docs/memex-oidc-verification.md` D1 and D2 in this
   subticket**, because that is where they become true; leaving it to
   R6f leaves the runbook wrong in between. Depends on nothing; keep it
   separate from R6d so a regression is attributable to the version, not
   the config.
4. **R6d — the second provider element, with two grant rules.** The
   `local`, the `data` block, the two templatefile vars, the extended
   `:148` array with the `app-memex-admins` rule FIRST, and its comment.
   Apply, targeting
   memex. Run S1 (now `2 provider(s).`), S2, W1, D1, D2, G1, G2.
   Depends on R6b and R6c.
5. **R6e — humans log in, both tiers.** Write the Q1 client config on the
   operator's machine, then V1 (reader, including the write denial), V6,
   V2 and V4, then V5. V5 carries a SECOND `roles.tf` edit and a second
   infrastructure apply — the operator joins `app-memex-admins` — so this
   subticket touches Terraform as well as a browser. Budget for THREE
   logins: reader, no-groups, and the dual-member admin login. Depends on
   R6d. The logins are the only steps that cannot be scripted.
6. **R6f — docs.** The `docs/memex-oidc-verification.md` S1 count, the
   new V1-V6 and G1-G5 section and the retitle; the
   `docs/vault-human-auth.md` consumer entry, own-key rule, loopback
   rule, id_token rule, the corrected break-glass paragraph (P24) and the
   config snippet; the `docs/cluster-roles.md:116-141` update recording
   `local.app_user_group_members` (R20); the supersession note on
   `.loop/archive/R5-rollout-memex-oidc-auth/eval.md`. Depends on R6e.

## 11. Open questions

**Q1 — where does the human's client config live, and in what form?**
Not settled by the request. memex reads client config from
`~/.config/memex/config.yaml`, from a `.memex.yaml` found by walking CWD
and its parents, or from `MEMEX_OIDC__*` env vars (P1). `scopes` is a
`list[str]`, and the env form of a list field is a JSON string, which is
easy to get wrong by hand.
*Recommendation: a YAML snippet at `~/.config/memex/config.yaml`,
documented in `docs/vault-human-auth.md`, run on the LAPTOP and not in
the devcontainer.*

```yaml
oidc:
  issuer: "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
  client_id: "<from terraform output or vault read>"
  credential: "id_token"
  scopes: ["openid", "groups"]
```

Laptop, not devcontainer, for a concrete reason: `memex auth login`
binds an ephemeral loopback port INSIDE whatever machine runs it (P10),
and a host browser cannot reach a container's `127.0.0.1:<random>`
without a port forward that cannot be declared in advance. Running it in
the devcontainer is a fork the operator can take, but it needs its own
answer for the callback and should not be assumed to work.

**Q2 — SETTLED 2026-08-04 by the operator. Two tiers, not one, and BOTH
are new app-user tiers.** Recorded here so it is not re-opened as a fork.

The single `developer` gate is replaced by two, both named in one
`vault_identity_oidc_assignment` so both can log in:

| memex policy | Vault group | Branch | Why |
|---|---|---|---|
| `admin` | a NEW `local.app_user_groups` entry, `app-memex-admins` | 2, a new app-user tier | Symmetric with the reader tier, and it keeps daily memex admin out of break-glass |
| `reader` | a NEW `local.app_user_groups` entry, `app-memex-readers` | 2, a new app-user tier | Branch 2 exists for exactly this and ships empty; the tier is explicitly for TESTING that the tiering works end to end |

`reader` is `Permission.READ` only, `admin` is READ + WRITE + DELETE
(P23), so the two tiers are genuinely different and the difference is
observable in one HTTP status (§8 V1, V5).

**Why NOT `vault_identity_group.admin` for the admin tier**, revised
2026-08-04 and worth keeping on the record: that group is break-glass.
`external_member_entity_ids = true`
(`deployments/infrastructure/roles.tf:131`) means Terraform owns the
group and not its membership, joining is a `vault write` no apply reverts
(`docs/cluster-roles.md:84-94`), and the file warns that leaving yourself
in it is invisible to every plan
(`deployments/infrastructure/roles.tf:125-126`). It also carries Vault's
wildcard policy (`:31-116`). Using it for daily memex admin would mean
living in break-glass. Two app-user tiers match the scaffold's stated
purpose (`:148-151`) and leave break-glass alone (R21).

The reader tier is a test instrument first. It proves that a non-admin
Vault group produces a genuinely reduced memex grant, which no other
check in this repo does today, and it gives the second `grant_rule` that
makes the ORDERING question real. It is not a claim that anyone will
live on `reader` day to day.

Two consequences the operator should hold in view:
- Membership of both tiers is a reviewed Terraform edit (R20), so who
  holds memex admin is visible in a plan. That reviewable list IS the
  control; no incident ritual gates it. See §9's closing note and Q8.
- `developer` is deliberately NOT one of the two (§5). It is the cluster
  tier with a real Vault policy; overloading it as a memex label would
  make a memex grant change require a cluster-privilege change.

**Q3 — SETTLED 2026-08-04 by the operator. A 30-day session on a
dedicated key, and BOTH TTLs at 30 days.** Recorded here with the part
that is not obvious.

The operator logs in about once a month, so the target is a ~30-day
session. The route:

| Field | Value | Why |
|---|---|---|
| `vault_identity_oidc_key.memex_human.rotation_period` | `604800` (7d) | The 10x rule: `verification_ttl` may not exceed 10x this (P18). 7d gives headroom over the 3d minimum 30d needs |
| `vault_identity_oidc_key.memex_human.verification_ttl` | `2592000` (30d) | The ceiling on the client's `id_token_ttl` (P17) |
| `vault_identity_oidc_client.memex.id_token_ttl` | `2592000` (30d) | The session |
| `vault_identity_oidc_client.memex.access_token_ttl` | `2592000` (30d) | **Not the short value the shape suggests. See below** |

**The dedicated key is the whole mechanism.** The cap is the
`verification_ttl` of the key THE CLIENT REFERENCES, and `key` is a
per-client field (P17). The repo's existing clients point at `lab`
(`oidc.tf:135`, `nomad_oidc.tf:46`) by choice; `lab` is at 86400, so a
client on it cannot exceed 24h. A second key costs one resource and
leaves `lab` alone (§5). It also creates the memex-only break-glass
levers in §9, which would not exist on a shared key.

**`access_token_ttl` is the trap, and the intuition is wrong.** Vault's
access token is an opaque batch token that memex never verifies, so the
instinct is to keep it short. That instinct breaks the feature: the memex
client caches `min(now + expires_in, id_token exp)`, and Vault's
`expires_in` is exactly the `access_token_ttl` (P21). At `3600` the
client would discard a 30-day id_token after an hour and fall back to the
API key, with every request still returning `200`. So the two TTLs are
COUPLED, and both are `2592000`. §8 V6 is the check; §9 mode 2 is the
failure.

The cost is honest and recorded in §9: a 30-day stateless bearer sitting
in a file on a laptop, revocable in full only by §9's FIRST lever, which
drops the client from the provider's allowed list. Rotation, the second
lever, reaches only the tokens issued since the last rotation (P24).
If the operator wants that shorter, 7 days (`604800`) is the obvious
alternative and needs no key change, only the two client TTLs.

**Q4 — how are R5's now-false eval rows handled?**
R5 is `done` and its marker is operator-signed
(`.loop/archive/R5-rollout-memex-oidc-auth/eval.md:26`). Three rows go false
when this lands: `:15` (S1, "1 provider(s)"), `:18` (D2, "the server log
emits NOTHING"), `:23` (G1, "exactly ONE element", "no
`vault_identity_oidc_client`").
*Recommendation: do not edit the signed rows.* An eval marker is a
point-in-time acceptance record of work already accepted, not a suite
that gets re-run; rewriting it erases what was actually signed off.
Append one supersession note below `:26` naming R6 and the three row
numbers, and carry the corrected assertions in R6's own eval and in
`docs/memex-oidc-verification.md`, which IS the artifact re-run. If the
operator would rather amend R5's marker in place, that is their call to
make before R6f, and it needs a fresh sign-off line.

**Q5 — when do the static API keys go?**
The operator settled *whether*: keep them. Only *when* is open. The
fallback is what makes §9 mode 9 a degradation rather than an outage,
and it is what the browser extension uses.
*Recommendation: a follow-up ticket, after the 30-day TTL has been lived
through at least once and V1 has held.* Removing `MEMEX_API_KEY` from
the operator's environment first (leaving the server keys for the
extension) is the smaller, reversible half and makes the silent
downgrade in §9 mode 9 loud, which is arguably worth doing sooner.

**Q6 — SETTLED, recorded so it is not re-opened.** `memex auth login
--device` cannot work against Vault. The `lab` provider advertises
`grant_types_supported: ["authorization_code"]` and no
`device_authorization_endpoint` (P2), and the memex CLI raises
`LoginError` when that endpoint is absent (P2). Browser login only. Do
not attempt to add device-flow support to Vault.

**Q7 — SETTLED 2026-08-04 by the operator. A sibling members map.**
Recorded here so it is not re-opened as a fork; it was blocking R6a and
no longer blocks anything.

`docs/cluster-roles.md:140-141` says "Adding a **person** to a tier is an
edit to `member_entity_ids`" and
`deployments/infrastructure/roles.tf:158-161` promises the same, but
`vault_identity_group.app_user` (`:165-177`) has no such field and
`local.app_user_groups` is a name-to-description map, so there was
nowhere to make that edit — and the provider writes `member_entity_ids`
authoritatively anyway (P22). The decision, which is R20:

```hcl
locals {
  app_user_group_members = {
    "app-memex-readers" = [vault_identity_entity.operator.id]
  }
}

# on vault_identity_group.app_user
member_entity_ids = lookup(local.app_user_group_members, each.key, [])
```

Why this over the two alternatives that were on the table (an
object-valued `local.app_user_groups` carrying description AND members,
or `external_member_entity_ids = true` plus
`vault_identity_group_member_entity_ids`):

- It leaves the documented map shape (`docs/cluster-roles.md:118-126`)
  and every consumer instruction intact.
- It is one `local` and one line on the resource, and defaults cleanly to
  `[]` for a tier with no members yet.
- It keeps the tier list reviewable in the repo, which is the property
  `deployments/infrastructure/roles.tf:172-174` protects.
- The third shape is the one that had to be avoided: the `for_each` is
  shared, so `external_member_entity_ids = true` would apply to EVERY
  future tier and hand the whole scaffold the opposite property from the
  one it was built for.

This is a shared-scaffold change that outlives the ticket. Every later
branch-2 consumer (M2's MinIO tiers, the F14 follow-ups) gets its member
list for free, and `docs/cluster-roles.md:140-141` stops being
aspirational. It is also why §9's expected-diff table matters: the same
edit grows F2's smoke assignment by derivation (P25).

**Q8 — SETTLED 2026-08-04 by the operator: END 1, both tiers.** Where the
two tiers' membership rests once §8 has run. Before the
2026-08-04 revision the answer was forced: `admin` had no members, so SSO
rested at `reader`. Now both tiers are Terraform-managed and `operator`
is the only human entity (P11), so the resting state is a choice. §8 runs
V1 with the operator in `app-memex-readers` only, then V5 adds
`app-memex-admins`. Three ends:

1. *Both tiers.* Every daily login is a dual-member login that must land
   on `admin`, so R19's ordering is re-exercised continuously and a
   regression shows up as a `403` on the first write instead of lying
   dormant.
2. *`app-memex-admins` only.* Cleanest reading of intent, but the reader
   `grant_rule` goes inert and the reader tier sits empty.
3. *`app-memex-readers` only, admin on demand.* Least privilege at rest,
   at the cost of a Terraform apply before any memex write.

*Recommendation: end 1, which is where §8 already leaves it, so it costs
no extra apply.* If the operator prefers 2 or 3, say so before R6e: the
change is one line in `local.app_user_group_members`. This does NOT block
R6a.

## Premises / assumptions

Evidence is a resolved `path:line`, a probe command with captured
output, or an explicit UNCERTAIN. Every probe below is read-only and was
run on 2026-08-03 or 2026-08-04 against the live cluster unless marked
otherwise.

**Do NOT verify any memex premise against a vendored `apm_modules` tree.**
That directory was deleted on 2026-08-03 precisely because it was a
stale pre-OIDC snapshot whose files resolved by bare basename to real
code saying something else. memex premises below cite upstream at tag
`v1.2.0` (or `v1.1.0` for the comparison) by URL. Vault's and Nomad's Go
sources are not vendored here either; those cite upstream tags.

**P1 — memex v1.2.0 adds a client-side `credential` setting, names
HashiCorp Vault, and requires the server's `audience` to be the
client_id. VERIFIED (upstream source, both the field and its
validation).**
`OidcClientConfig.credential` is
`Literal['access_token', 'id_token'] = Field(default='access_token', ...)`.
Its validator raises unless `grant == 'interactive'` ("Service-account
and keyless grants never receive an id_token") and unless `'openid' in
self.scopes`. The v1.2.0 how-to states it directly: "An id_token's `aud`
is the **client id**, not a separate API identifier, so the server's
`audience` must list the client id" (line 115), and "Setting `scopes`
replaces the default list rather than adding to it, so spell out
everything you need" (line 113). Provider selection is by `iss`, then
signature, `aud`, `iss` and `exp` (how-to line 40). `_rule_matches` does
membership on a list claim and equality on a scalar
(`packages/core/src/memex_core/server/oidc.py` lines 86-97 at v1.2.0).
Source:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/common/src/memex_common/config.py>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/core/src/memex_core/server/oidc.py>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/docs/how-to/configuring-server/oidc.md>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/docs/reference/configuration-options.md>

**P2 — the Vault `lab` provider offers authorization_code only, no
device endpoint, and no refresh-token grant. VERIFIED (live,
read-only).**
probe:
`curl -sk https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration`

```
issuer                          : https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab
grant_types_supported           : ["authorization_code"]
scopes_supported                : ["groups", "openid"]
code_challenge_methods_supported: ["plain", "S256"]
token_endpoint_auth_methods_supported: ["none", "client_secret_basic", "client_secret_post"]
(no device_authorization_endpoint key)
```

The memex CLI raises `LoginError('provider does not advertise a
device_authorization_endpoint.')` when that key is absent
(`memex_cli/auth.py` at v1.2.0, the `_device_login` path). Vault's token
response is built as
`{"token_type", "access_token", "id_token", "expires_in"}` with no
`refresh_token` key (Vault v2.0.3
`vault/identity_store_oidc_provider.go` lines 2166-2171). Together: browser
login only, and re-login at expiry rather than refresh. This settles Q6
and drives §9 mode 9.
Source:
<https://github.com/JasperHG90/memex/blob/v1.2.0/packages/cli/src/memex_cli/auth.py>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>

**P3 — a PUBLIC PKCE client is accepted by this provider. VERIFIED
(live, same probe as P2).**
`token_endpoint_auth_methods_supported` contains `none`, which is what
makes `client_type = "public"` viable, and
`code_challenge_methods_supported` contains `S256`. Vault also REQUIRES
PKCE for a public client: `if !okCodeChallenge && client.Type == public
{ return ... "PKCE is required for public clients" }` (Vault v2.0.3
`pathOIDCAuthorize`). The memex CLI always sends
`code_challenge_method: 'S256'` with a fresh verifier
(`memex_cli/auth.py` at v1.2.0, `_loopback_login`). Contrast
`deployments/infrastructure/nomad_oidc.tf:54`, which is `confidential`
because the Nomad server holds the secret.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>

**P4 — a Vault id_token's `aud` IS the client id, and its `iss` is the
provider issuer. VERIFIED (upstream source) and corroborated in this
repo.**
Vault builds the token as `idToken{ Issuer: provider.effectiveIssuer,
Subject: authCodeEntry.entityID, Audience: authCodeEntry.clientID, ... }`
(Vault v2.0.3 `pathOIDCToken`). The repo already depends on this in
production: `deployments/infrastructure/nomad_oidc.tf:154` binds
`bound_audiences = [vault_identity_oidc_client.nomad.client_id]` against
this same provider, and that login works. This is what makes R2's
`audience` differ from R5's `["memex"]`.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>

**P5 — the memex container reaches the Vault `lab` discovery and JWKS
over TLS with its own trust store, and that JWKS is RS256. VERIFIED
(live, from inside the running alloc).**
probe: `nomad alloc exec -task memex <alloc> python3 -c
"urllib.request.urlopen(...)"`, no `verify=False`:

```
200 https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration
200 https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/keys
200 https://nomad.lab.orangecluster.nl/.well-known/openid-configuration
keys: [{'kty':'RSA','alg':'RS256','use':'sig'} x3]
```

So the private CA is trusted in-container for the Vault host as well as
the Nomad one, which is the requirement memex's how-to states (line
242). RS256 is inside memex's default
`algorithms: ["RS256","ES256"]` (P1), so no override is needed — and the
new `memex-human` key is `algorithm = "RS256"` for the same reason. The
issuer string above is what `local.vault_oidc_issuer` must carry
byte-for-byte. Note Vault's `jwks_uri` ends `/.well-known/keys`, not
`jwks.json`; memex discovers it rather than assuming (P1).

**P6 — v1.2.0 changes four server log paths, and one of them INVERTS
R5's D2 check. VERIFIED (upstream source, both tags compared).**
At v1.1.0 `OidcVerifier.verify` had four `logger.info` calls (a fifth
sits outside it, on the module-level startup path) and
was SILENT on both the unparseable-token path (`return None` with no
log) and the unknown-issuer path, and `_claims_to_context` returned
`None` with no log when no `grant_rule` matched. That silence is exactly
what R5's D2 asserts (`docs/memex-oidc-verification.md:152-155`).

At v1.2.0 the same function logs, at `warning`:

- `OIDC bearer rejected: not a parseable JWT (%d dot-separated segments). ...`
  (new; `packages/core/src/memex_core/server/oidc.py` lines 182-188)
- `OIDC bearer rejected: no configured provider matches issuer %s. Configured issuers: %s.`
  (new; `:200-205`)
- `OIDC token rejected for issuer %s: %s` (was `info`; D1's line; `:251`)
- `OIDC token verified for issuer %s but matched no grant_rule and the
  provider has no default_policy, so it authorizes nothing. Claims
  present on the token: %s.` (new; D2's line; `:265-271`)

So on v1.2.0 a healthy D2 EMITS a line and D2-as-written fails a working
system. §7 rewrites it and §8 carries the new assertion.
Source:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.1.0/packages/core/src/memex_core/server/oidc.py>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/core/src/memex_core/server/oidc.py>

**P7 — the v1.2.0 bump is safe for R5's workload path, the image exists,
and no migration rides along. VERIFIED (upstream diff, plus a live
registry probe).**
The v1.1.0-to-v1.2.0 compare returns 71 files over 9 commits, of which
exactly FOUR are non-test source: `packages/cli/src/memex_cli/auth.py`,
`packages/common/src/memex_common/auth_client.py`,
`packages/common/src/memex_common/config.py`, and
`packages/core/src/memex_core/server/oidc.py`. The rest are their tests
and harness artifacts. No
migration, schema, or API file. In `auth_client.py`,
`resolve_client_headers` and `_read_workload_token` are byte-identical
across the two tags, and `_resolve_bearer` changes only its interactive
branch — its `if oidc.grant in ('token_file', 'token_env')` branch is
first and unchanged. In `config.py` the ONLY change is the `credential`
field and its validator, which fires only when `credential ==
'id_token'`, so R5's `grant: token_file` config validates unchanged.
probe (registry, read-only, credentials from `.devcontainer/.env`):

```
GET https://ghcr.io/v2/jasperhg90/memex-jetson/tags/list  ->  ... "1.1.0","1.2.0"
```

So `ghcr.io/jasperhg90/memex-jetson:1.2.0` exists, and hermes's bundled
v1.1.0 client needs no bump (§5).
Source: <https://github.com/JasperHG90/memex/compare/v1.1.0...v1.2.0>

**P8 — Vault IGNORES unsupported scopes rather than rejecting them, so a
missing `groups` scope fails silently. VERIFIED (upstream source, plus a
live probe that could not distinguish and is reported as such).**
`pathOIDCAuthorize` requires `openid` and then filters:
`for _, scope := range requestedScopes { if
strutil.StrListContains(provider.ScopesSupported, scope) && scope !=
openIDScope { scopes = append(scopes, scope) } }`. Only the surviving
scopes reach `populateScopeTemplates`, which is what emits the `groups`
claim. So memex's default scope list `["openid","profile","email",
"offline_access"]` (P1) authorizes fine and yields a token with NO
`groups` claim.
probe: four authorize calls varying only `scope`
(`openid`; `openid groups`; `openid profile email offline_access`;
`openid groups offline_access`) all returned the identical
`{"error":"access_denied","error_description":"identity entity must be
associated with the request"}`. That is consistent with the source and
NOT a proof of it: the entity check sits after the scope filter, so the
probe cannot discriminate. The source is the evidence; the probe only
rules out an outright scope rejection. This drives R7 and §9 mode 1.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>,
`docs/vault-human-auth.md:300-306`

**P9 — with no refresh token the client falls back to the API key at
expiry. VERIFIED (upstream source).**
`_resolve_bearer` at v1.2.0: when the cache is stale and
`not cache.refresh_token`, it logs `Cached OIDC token expired and no
refresh token is available.` and returns `None`;
`resolve_client_headers` then returns `{'X-API-Key': ...}` when
`config.api_key` is set, else `{}`. It also raises rather than falling
back when the response carries no id_token. This drives §9 mode 9 and
Q5. The expiry arithmetic itself is P21.
Source:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/common/src/memex_common/auth_client.py>

**P10 — Vault matches loopback redirects port-agnostically on BOTH
sides, exactly on scheme, host literal and path; memex binds an
ephemeral port. VERIFIED (live probe for the denial, upstream source for
the grant).**
probe, against the existing `nomad` client
(`client_id=CFIY4Ai7WsIUIJBDAgPNStfeCn6wAiAG`, registered URIs at
`deployments/infrastructure/nomad_oidc.tf:48-51`), using a root token so
`access_denied` means the redirect check PASSED:

```
http://localhost:4649/oidc/callback   => access_denied
http://localhost:59999/oidc/callback  => access_denied
http://127.0.0.1:4649/oidc/callback   => invalid_redirect_uri
```

Row 2 is the port-agnostic match; row 3 is the exact host-literal match.
R5's review left open whether a REGISTERED `127.0.0.1` URI is itself
treated as loopback. It is: `validRedirect` keys the loopback branch on
the INPUT's hostname and then strips the port from the registered side
too (`allowedURI.Host = allowedURI.Hostname()`) before comparing. The
ordering in `pathOIDCAuthorize` also matters for §8's V3: client,
redirect, provider `allowed_client_ids`, and scope are all checked
BEFORE `req.EntityID == ""`. memex's side: the CLI binds
`http.server.HTTPServer(('127.0.0.1', 0), _Handler)` and builds
`redirect_uri = f'http://127.0.0.1:{port}/callback'`, so the port cannot
be registered in advance.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider_util.go>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>,
<https://github.com/JasperHG90/memex/blob/v1.2.0/packages/cli/src/memex_cli/auth.py>

**P11 — one human entity exists, it is in `developer` and `oidc-smoke`,
and `admin` has NO members. VERIFIED (live, read-only, re-run
2026-08-04).**
probe: `vault read identity/entity/name/operator` then
`vault read identity/group/name/<g>` for each group:

```
operator entity 351f302a-ada1-0e79-15d3-e22a4be2e3e4
  -> groups [e86ec229-... (oidc-smoke), 64780816-... (developer)]
developer   64780816-f386-a2d8-b019-28ab585c6cfe  members [351f302a-...]
oidc-smoke  e86ec229-b3fd-70ec-4f3b-d1a2ded3dbb5  members [351f302a-...]
admin       d40f1623-23ce-957b-1b81-afb921207923  members None
```

The `groups` claim is a LIST of group NAMES, which `_rule_matches`
handles by membership (P1). Three consequences this plan leans on:
`operator` is the only entity that can exercise either tier
(`deployments/infrastructure/auth_userpass.tf:38-44` is the only
`vault_identity_entity` in the root), which is also why the smoke
assignment's growth changes no effective access (P25); `admin` admits
nobody and this ticket leaves it that way (R21), so
`vault read identity/group/name/admin` still reporting no members after
apply is G5's break-glass check; and both new tiers show up in this same
claim once R20's membership lands. Terraform sources:
`deployments/infrastructure/developer_group.tf:158-164`,
`deployments/infrastructure/roles.tf:127-136`.

**P12 — `client_type` is immutable. VERIFIED (upstream source).**
`pathOIDCCreateUpdateClient` returns
`"client_type modification is not allowed"` on an update that changes it
(`vault/identity_store_oidc_provider.go` lines 1147-1149). The `key` field
carries the same restriction; the TTL ceiling that used to be recorded
here now lives in P17, because a dedicated key moves it.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>

**P13 — `data "vault_identity_oidc_client_creds"` is available in the
applications root and handles a PUBLIC client. VERIFIED (provider binary
probe, plus the provider's source).**
probe: `strings` over
`deployments/applications/.terraform/providers/registry.terraform.io/hashicorp/vault/5.3.0/linux_arm64/terraform-provider-vault_v5.3.0_x5`
lists `vault_identity_oidc_client_creds` alongside
`vault_identity_oidc_client`. Its read function branches on the client
type: `clientSecret := ""; if clientType != "public" { clientSecret =
creds.Data["client_secret"].(string) ... }`, and errors with
`no client found at %q` when the client is absent, which is §9 mode 4's
loud failure. Vault itself omits `client_secret` from a public client's
read response (`pathOIDCReadClient`: `if client.Type == confidential`).
Neither root has an `outputs.tf` or a `terraform_remote_state` block, so
this data source is the cross-root channel.
Source:
<https://github.com/hashicorp/terraform-provider-vault/blob/v5.3.0/vault/data_identity_oidc_client_creds.go>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>

**P14 — R5 IS APPLIED: memex runs v1.1.0 with exactly one OIDC provider,
key auth intact, and emits INFO records to its log. VERIFIED (live,
read-only, 2026-08-04).**
probe: `nomad job status memex` reports version 42, one healthy alloc
(`6ae458c1`), running. `nomad job inspect memex | grep -c
MEMEX_SERVER__AUTH__OIDC` returns `1`, where it returned `0` when this
plan was first written. The startup lines:

```
info  API key authentication enabled (3 key(s) configured, 3 exempt path(s)). [memex.core.server]
info  OIDC bearer-token authentication enabled (1 provider(s)).              [memex.core.server]
```

That is S1's `1` today and its `2` after R6d, and it is what makes the
INFO line observable at all (the v1.2.0 how-to notes it is below the
default WARNING level, line 73). R5's baseline triple against
`http://192.168.2.46:8000/api/v1/vaults` was `401` / `403` / `200`;
re-measure it before starting rather than trusting this line.

**P15 — the repo's gates here are the pre-commit hooks plus per-root
`terraform validate`, with no Python gate. VERIFIED.**
`.pre-commit-config.yaml:16-21` is `nomad-fmt`, `:22-27`
`terraform-fmt`, `:28-33` `terraform-validate` running
`scripts/tf_validate.sh`, which validates
`deployments/infrastructure`, `deployments/applications` and
`deployments/applications/modules/bucket` offline
(`scripts/tf_validate.sh:8-20`). The Python hooks are scoped
`files: '^cli/'` (`.pre-commit-config.yaml:37-53`).
`.pre-commit-config.yaml:1` excludes `.loop/`, so the eval note in §7 is
not gated. `.loop/config.json` sets `gates: ["just pre_commit"]`,
`require_review: true`, `require_eval: true`. `just pre_commit` is
`justfile:18-19`; `just worktree_setup` is `justfile:44`; the
applications apply recipe takes positional `refresh` then `target`
(`deployments/applications/justfile:13-24`) and the infrastructure one
takes neither (`deployments/infrastructure/justfile:11-13`).

**P16 — the cluster runs Vault 2.0.3, which is the tag every Vault
source citation above uses. VERIFIED (live, re-confirmed 2026-08-04).**
probe: `curl -sk https://vault.lab.orangecluster.nl/v1/sys/health` reports
`"version":"2.0.3"`, matching the pin at
`bootstrap/inventory/group_vars/all.yml:11` (`vault: 2.0.3-1`). Note
this differs from Nomad, which R5 measured at 2.0.4
(`bootstrap/inventory/group_vars/all.yml:12`) — do not conflate the two
when re-checking a source citation.

**P17 — a client's `id_token_ttl` is capped by the key THAT CLIENT
references, `key` is per-client and immutable, and the key registration
is checked at the TOKEN endpoint. VERIFIED (upstream source at v2.0.3,
plus live config).**
`pathOIDCCreateUpdateClient` resolves the client's own key and then caps
against it:

```go
// vault/identity_store_oidc_provider.go line 1115
key, err := i.getNamedKey(ctx, req.Storage, client.Key)
...
// :1135-1137
if client.IDTokenTTL > key.VerificationTTL {
    return logical.ErrorResponse("a client's id_token_ttl cannot be greater than the verification_ttl of the key it references"), nil
}
```

`key` is per-client and cannot be changed afterwards:
`"key modification is not allowed"` (`:1106-1108`). The key cannot be
deleted while a client references it: `unable to delete key ...
clients` (`vault/identity_store_oidc.go` lines 858-866). And the registration
is enforced at the token exchange, not at authorize:

```go
// vault/identity_store_oidc_provider.go lines 1982-1986
if !strutil.StrListContains(key.AllowedClientIDs, "*") &&
   !strutil.StrListContains(key.AllowedClientIDs, clientID) {
    return tokenResponse(nil, ErrTokenInvalidClient, "client is not authorized to use the key")
}
```

live, read-only: `vault read identity/oidc/key/lab` reports
`rotation_period 86400`, `verification_ttl 86400`, and
`allowed_client_ids` holding exactly the smoke and nomad client ids. So
a client on `lab` is capped at 24h, and the ONLY way to a 30-day
id_token without touching `lab` is a second key. This is R17, R18, the
§7 resource list, §9 mode 3 and mode 8, and §8's V3 caveat.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc.go>

**P18 — Vault's key rules: `verification_ttl` <= 10x `rotation_period`,
`rotation_period` >= 1 minute, and a rotated-out public key stays
verifiable for `verification_ttl`. VERIFIED (upstream source at
v2.0.3).**

```go
// vault/identity_store_oidc.go lines 574-576
if key.RotationPeriod < 1*time.Minute {
    return logical.ErrorResponse("rotation_period must be at least one minute"), nil
}
// :584-586
if key.VerificationTTL > 10*key.RotationPeriod {
    return logical.ErrorResponse("verification_ttl cannot be longer than 10x rotation_period"), nil
}
```

So `604800` / `2592000` is legal (30d is 4.3x 7d) and, for example,
`86400` / `2592000` is not. On rotation the OUTGOING public key gets
`ExpireAt = now + verificationTTL` and stays in the key ring
(`:1715-1722`); the periodic function drops ring members whose
`ExpireAt` has passed (`:1997-2016`). That is what lets a 30-day token
survive four intervening 7-day rotations. `rotate` also accepts a
`verification_ttl` override (`:944-950`), which §9's second break-glass
lever uses — but its reach is far narrower than that one line suggests.
The measurement of that reach is P24; §9 states it.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc.go>

**P19 — the provider's JWKS is built from the keys ITS ALLOWED CLIENTS
reference, so a client-specific key publishes automatically; memex
caches that JWKS for an hour. VERIFIED (upstream source plus a live
probe).**
`pathOIDCReadProviderPublicKeys` builds the JWKS from
`i.keyIDsReferencedByTargetClientIDs(ctx, req.Storage,
provider.AllowedClientIDs)`
(`vault/identity_store_oidc_provider.go` line 1607), and that helper walks
each allowed client id, collects `client.Key`, and emits every KeyID in
that key's ring (`:1643-1691`). So appending the memex client to
`local.oidc_provider_client_ids` is ALSO what publishes the
`memex-human` key, and removing that one line is what unpublishes it
(§9's first break-glass lever).
probe, live and read-only:
`curl -sk https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/keys`

```
n_keys 3   [{kid d74dab14, RS256}, {kid b9670e2d, RS256}, {kid a48d3095, RS256}]
```

Three today, all from the `lab` key's ring, matching its two allowed
clients. Expect this to GROW at R6b. On the memex side the JWKS is
cached for `_JWKS_CACHE_TTL_SECONDS = 3600.0`
(`packages/core/src/memex_core/server/oidc.py` line 46), with a forced
refetch on an unknown `kid` rate-limited to once per 30 s per issuer
(`:216-238`). The forced refetch is what makes a 7-day rotation
invisible to users; the 3600 s cache is why revocation is not instant.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/core/src/memex_core/server/oidc.py>

**P20 — memex takes the FIRST matching `grant_rule` and stops. VERIFIED
(upstream source at v1.2.0).**

```python
# packages/core/src/memex_core/server/oidc.py lines 106-117
for rule in provider.grant_rules:
    if _rule_matches(claims, rule):
        policy = rule.policy
        ...
        break
else:
    if provider.default_policy is None:
        return None
```

The config field says the same: `grant_rules` is
`'Claim-to-policy mapping rules, evaluated in order (first match wins).'`
(`packages/common/src/memex_common/config.py` lines 1530-1532), and
`OidcGrantRule`'s docstring repeats it (`:1399-1407`). So with the
`admin` rule at index 0, a token whose `groups` claim carries BOTH
`admin` and `app-memex-readers` resolves to `admin`; swap the order and
the same token resolves to `reader`, with no log line either way. This
is R19 and §8's V5.
Source:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/core/src/memex_core/server/oidc.py>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/common/src/memex_common/config.py>

**P21 — the memex client's session is `min(now + expires_in, id_token
exp)`, and Vault's `expires_in` IS the `access_token_ttl`, uncapped.
VERIFIED (upstream source, both sides).**
memex, under `credential='id_token'`:

```python
# packages/common/src/memex_common/auth_client.py lines 180-193
expires_in = float(data.get('expires_in', 3600))
expires_at = time.time() + expires_in
...
    id_exp = _jwt_exp(id_token)
    # `expires_in` describes the ACCESS token
    expires_at = min(expires_at, id_exp)
```

Vault, on the other side:

```go
// vault/identity_store_oidc_provider.go lines 2079-2080 and 2170
accessTokenExpiry := accessTokenIssuedAt.Add(client.AccessTokenTTL)
...
"expires_in": int64(accessTokenExpiry.Sub(accessTokenIssuedAt).Seconds()),
```

so the reported `expires_in` is exactly `access_token_ttl`. Nothing caps
it on the way out: the access token is a BATCH token, and the batch
branch of `CreateToken` passes `entry.TTL` straight into the marshalled
entry with no lease-TTL clamp
(`vault/token_store.go` lines 1206-1225). For context the cluster leaves
`default_lease_ttl` and `max_lease_ttl` at `0` (live:
`vault read sys/config/state/sanitized`), which means Vault's built-in
32 days (`vault/expiration.go` line 61, `maxLeaseTTL = 32 * 24 * time.Hour`),
comfortably above 30.

Conclusion, and it is the opposite of the intuition: a short
`access_token_ttl` next to a 30-day `id_token_ttl` caps the SESSION at
the short value, because memex takes the min. Both must be `2592000`.
This is R18, Q3, §8 V6 and §9 mode 2.
Source:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/common/src/memex_common/auth_client.py>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc_provider.go>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/token_store.go>,
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/expiration.go>

**P22 — an app-user tier has nowhere to record members today, and the
provider writes that field authoritatively. VERIFIED (repo source plus
provider source at the pinned 5.3.0).**
`vault_identity_group.app_user`
(`deployments/infrastructure/roles.tf:165-177`) sets `name`, `type`,
`policies` and `metadata`, and NO `member_entity_ids`.
`local.app_user_groups` (`:152-163`) is a map of name to DESCRIPTION, so
there is no per-tier place to put an entity id either. The provider,
with `external_member_entity_ids` unset (default `false`), writes the
config's value on create and on any tracked change:

```go
// terraform-provider-vault vault/resource_identity_group.go lines 144-147 (create)
if d.Get("type").(string) == "internal" {
    if externalMemberEntityIds, ok := d.GetOk("external_member_entity_ids"); !(ok && externalMemberEntityIds.(bool)) {
        data["member_entity_ids"] = d.Get("member_entity_ids").(*schema.Set).List()
// same file, lines 159-167 (update, gated on d.HasChanges(..., "member_entity_ids", ...))
```

so a tier created now is created EMPTY and a hand-added member is
reverted, exactly as `roles.tf:172-174` and
`docs/cluster-roles.md:102-105` intend. The provider does ship
`vault_identity_group_member_entity_ids` (probe: `strings` over
`deployments/infrastructure/.terraform/providers/registry.terraform.io/hashicorp/vault/5.3.0/linux_arm64/terraform-provider-vault_v5.3.0_x5`
lists it), but using it needs `external_member_entity_ids = true` on the
group, which the shared `for_each` would apply to every tier. This is
R20 (Q7, settled) and §9 mode 6.
Source:
<https://raw.githubusercontent.com/hashicorp/terraform-provider-vault/v5.3.0/vault/resource_identity_group.go>

**P23 — memex `reader` is READ only, and the write route named in §8 is
guarded by `require_write`. VERIFIED (upstream source at v1.2.0).**

```python
# packages/common/src/memex_common/config.py lines 1318-1330
class Policy(str, Enum):
    READER = 'reader'; WRITER = 'writer'; ADMIN = 'admin'

POLICY_PERMISSIONS = {
    Policy.READER: frozenset({Permission.READ}),
    Policy.WRITER: frozenset({Permission.READ, Permission.WRITE}),
    Policy.ADMIN:  frozenset({Permission.READ, Permission.WRITE, Permission.DELETE}),
}
```

`require_write = require_permission(Permission.WRITE)`
(`packages/core/src/memex_core/server/auth.py` line 288), and the route §8
uses declares it:
`@router.patch('/notes/{note_id}/title', dependencies=[Depends(require_write)])`
(`packages/core/src/memex_core/server/notes.py` line 370). The dependency
runs before `rename_note`, so a `reader` gets `403` and a fabricated
note id never reaches the handler — which is what makes it a safe probe.
Anything above `reader` gets past the gate and fails on the id instead,
which is the discriminator §8 V1 and V5 rely on.
Source:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/common/src/memex_common/config.py>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/core/src/memex_core/server/auth.py>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.2.0/packages/core/src/memex_core/server/notes.py>

**P24 — `rotate` stamps `ExpireAt` on the CURRENT signing key ONLY, so
repeated rotation never reaches older ring keys, and lowering
`verification_ttl` does not re-stamp them either. VERIFIED (upstream
source at v2.0.3).**

```go
// vault/identity_store_oidc.go lines 1715-1722, inside namedKey.rotate (lines 1708-1760)
if k.SigningKey != nil {
    // set the previous public key's expiry time
    for _, key := range k.KeyRing {
        if key.KeyID == k.SigningKey.KeyID {
            key.ExpireAt = now.Add(verificationTTL)
            break
        }
    }
}
...
// :1740
k.SigningKey = k.NextSigningKey
```

The loop `break`s on the one ring member whose `KeyID` matches the
CURRENT `SigningKey`, then `:1740` promotes `NextSigningKey`. Keys
rotated out at earlier rotations already carry the `ExpireAt` they were
stamped with at the time (up to `verification_ttl`, here 30 days), and no
path revisits them: the periodic function only DROPS ring members whose
`ExpireAt` has already passed (`:1997-2016`).

Two consequences §9's break-glass depends on:

- Calling `rotate verification_ttl=0` twice reaches no further back. The
  second call stamps the key the first call had just promoted, which has
  signed nothing in between. With `rotation_period = 604800` and
  `verification_ttl = 2592000` the ring holds roughly four rotated-out
  keys that DID sign still-live tokens, and rotation cannot expire any of
  them.
- The obvious escape hatch is shut. The key UPDATE path (`:568-676`) sets
  `RotationPeriod`, `VerificationTTL`, `AllowedClientIDs` and `Algorithm`
  and never touches `KeyRing[i].ExpireAt`, so lowering `verification_ttl`
  leaves existing ring members exactly as stamped. Vault also refuses
  that update outright while a referencing client's `id_token_ttl`
  exceeds the new value: `"unable to update key %q because it is
  currently referenced by one or more clients with an id_token_ttl
  greater than %d seconds"` (`:606-621`), which is precisely this
  client's situation.

So lever 2 revokes tokens issued since the last rotation, not all
outstanding tokens. Lever 1 — dropping the client from
`local.oidc_provider_client_ids`, which unpublishes the key from the
provider JWKS (P19) — is the complete one. This corrects the claim §9
carried before 2026-08-04, and it is the text §7 publishes into
`docs/vault-human-auth.md`.
Source:
<https://github.com/hashicorp/vault/blob/v2.0.3/vault/identity_store_oidc.go>

**P25 — every `local.app_user_groups` entry lands in F2's smoke
assignment by derivation, so adding two tiers grows it from one group id
to three. VERIFIED (repo source, both ends of the chain re-opened
2026-08-04).**
`local.all_app_user_group_ids = values(local.app_user_group_ids)`
(`deployments/infrastructure/roles.tf:199-201`), where
`local.app_user_group_ids` is
`{ for k, g in vault_identity_group.app_user : k => g.id }` (`:192-194`).
Its only consumer is `vault_identity_oidc_assignment.smoke`:

```hcl
# deployments/infrastructure/oidc.tf:129
group_ids  = concat([vault_identity_group.smoke.id], local.all_app_user_group_ids)
```

`local.app_user_groups` is empty today (`roles.tf:152-163`), so that list
holds exactly `vault_identity_group.smoke.id`. Adding `app-memex-admins`
and `app-memex-readers` makes it three, with no line of `oidc.tf`
changing.

The coupling is deliberate and both files say so: "Every tier id, for the
smoke client only. It is F2's throwaway proof that the extension point is
wired, so admitting all tiers is what it is for. A real consumer must NOT
use this." (`roles.tf:196-198`), plus the DO-NOT-COPY comment at
`oidc.tf:125-128`.

Effective access does not change today. The assignment gates who may
complete a login against the SMOKE client; `operator` is the only human
entity (P11) and is already a member of `vault_identity_group.smoke`
(`oidc.tf:114`, corroborated by P11's live probe, which lists
`oidc-smoke` among the entity's groups). The growth is real and belongs
in §9's expected-diff table and in G5. It is not a reason to rewrite F2's
file.
