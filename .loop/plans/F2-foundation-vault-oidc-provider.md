---
epic = "foundation"
depends_on = ["T3-tls-edge-cutover-lab-domain", "A1-audit-plan-premise-sweep"]
priority = 50
summary = "Stand up Vault's OIDC identity provider (key, scopes, clients, assignments, provider, and the identity groups they gate on) purely in Terraform, so every human OIDC login consumes one shared issuer."
tags = ["vault", "oidc", "terraform"]
---

# F2 — Vault OIDC provider scaffolding (foundation)

## 1. Title

Stand up Vault's OIDC identity provider (key, scopes, clients,
assignments, provider, and the identity groups they gate on) purely in
Terraform under `deployments/infrastructure/`, so that every human OIDC
login (MinIO console M2, oauth2-proxy landing page L1) consumes one
shared issuer.

## 2. Size / Effort

**Medium.** The resource graph is small (~6 resource types) and drops
into an already-wired Terraform root with the Vault provider present.
Effort is driven by (a) getting the `vault_identity_oidc_*` schema
exactly right against provider `5.3.0`, (b) the human-auth-backend fork
(none exists today), and (c) redirect-URI / issuer values that depend on
downstream tickets (L1, M2) not yet built.

## 3. Triggered by

Home-lab auth epic. CONFIRMED decision: **Vault is the OIDC provider
(IdP) for humans**; Zitadel was evaluated and dropped. F2 is the
keystone ticket: the same Vault OIDC scaffolding is consumed by MinIO
console (M2), oauth2-proxy for the landing page (L1), and every human
OIDC login.

## 4. Context

Today's state in `deployments/infrastructure/` (Terraform, Consul
backend, applied with `just apply`):

- The Vault provider is already declared and configured:
  `deployments/infrastructure/providers.tf:7-10` pins
  `hashicorp/vault` `~>5.3.0`; `providers.tf:28` has an empty
  `provider "vault" {}` (reads `VAULT_ADDR` / `VAULT_TOKEN` from the
  environment). The lockfile resolves this to exactly `5.3.0`
  (`deployments/infrastructure/.terraform.lock.hcl`).
- The only Vault resources that exist today are a KV2 mount and secrets:
  `deployments/infrastructure/secrets.tf:2-7` (`vault_mount "kvv2"`) and
  the `vault_kv_secret_v2` + `random_password` pattern at
  `secrets.tf:10-29` (MinIO creds), `:47-66` (Grafana), `:69-88`
  (Postgres). **No `vault_identity_*` / OIDC resources exist anywhere.**
- **No human auth backend exists.** A repo-wide search finds only a
  workload JWT auth method for Nomad
  (`bootstrap/roles/nomad_server/tasks/main.yml:198-255`,
  `jwt-nomad/`). There is no `userpass`, `oidc`, or `ldap` auth method
  for humans, and no `vault_identity_entity` / group resources. This is
  the central prerequisite fork (see Open Questions Q1).
- **HOSTNAME CHANGE, 2026-07-25, LANDED.** The references below now read
  `vault.lab.orangecluster.nl` and are current. F3's TLS shipped an unusable
  wildcard (`*.localstack` cannot match a hostname), so the edge moved to
  `*.lab.orangecluster.nl` with a
  publicly-trusted Let's Encrypt cert. This ticket's `depends_on` was
  retargeted from F3 to T3 for that reason: an OIDC **issuer URL** is baked
  into client configs and issued tokens, so committing to an issuer before
  the rename would have meant re-issuing it. The issuer is now
  `https://vault.lab.orangecluster.nl` over a certificate clients already
  trust, which also removes F2-Q2's https-issuer obstacle entirely.
- Vault is reachable at `http://vault.lab.orangecluster.nl` (haproxy host ACL
  `deployments/infrastructure/services/haproxy.hcl:53`, routed by
  `:66` to backend `vault1 192.168.2.30:8200` at `:91`). The Vault
  listener runs **plaintext HTTP** (`tls_disable = true`,
  `bootstrap/roles/vault_server/templates/vault.hcl.j2:17-20`;
  `api_addr = http://…:8200` at `:7`).
- Relying-party hosts that will consume the issuer: MinIO console at
  `minio.lab.orangecluster.nl` (haproxy `:51`, `:64`, backend `:84-85` →
  `192.168.2.29:9001`); the landing page (oauth2-proxy, L1) has **no
  host defined yet**.

What is missing: the entire OIDC identity provider stack, plus the
identity groups (`minio-admins`, `minio-readers`, `minio-writers`,
`dashboard-users`) that the per-client assignments gate on.

## 5. Non-goals / out of scope

- **Not** deploying any new Nomad job, container, or service. This is
  pure Terraform against the already-running Vault. No changes to
  `services.tf` or `services/*.hcl`.
- **Not** adding a new Terraform provider (the Vault provider is already
  present).
- **Not** configuring MinIO's OIDC settings or oauth2-proxy itself —
  those are M2 and L1. F2 only produces the issuer + clients + secrets
  they will consume.
- **Not** standing up the human auth backend or enrolling real human
  users (see Q1 — this may be a follow-up ticket once the backend is
  chosen). F2 creates the identity groups and, if the operator picks a
  backend, the entity-alias wiring; otherwise it leaves groups with
  empty membership and documents the prerequisite.
- **Not** terminating TLS for Vault or changing the haproxy/listener
  config.

## 6. Requirements & restrictions

Must achieve:

- A working Vault OIDC issuer: `vault_identity_oidc_key`,
  `vault_identity_oidc_scope`, `vault_identity_oidc_client` (one per
  relying party), `vault_identity_oidc_assignment`, and
  `vault_identity_oidc_provider`, such that the discovery endpoint
  (`/.well-known/openid-configuration`) and JWKS are reachable and a
  test client can complete an auth-code flow.
- Vault identity groups `minio-admins`, `minio-readers`,
  `minio-writers`, `dashboard-users`, referenced by the per-client
  assignments (this is the per-tier gating mechanism M2 depends on).
- A scope with a claim template that exposes the group/entity claim
  relying parties (MinIO, oauth2-proxy) read (the group-membership
  claim).
- OIDC clients for: oauth2-proxy (landing page, L1) and the MinIO
  console tiers (the three tier-clients are detailed in M2, but the
  provider + key + scope live here).

Restrictions the repo enforces (cite where stated):

- **Secrets live in Vault KV2, never hardcoded** (`CLAUDE.md` Key
  Conventions; pattern at `secrets.tf:15-29`). Any generated OIDC
  `client_secret` must be written to the KV2 mount
  (`vault_mount.kvv2.path`) following the existing `vault_kv_secret_v2`
  shape so the downstream RP jobs can template it — not committed to
  the repo. `detect-private-key` runs in pre-commit
  (`.pre-commit-config.yaml:12`).
- **Surgical, minimum change** (`CLAUDE.md` §2, §3): no speculative
  clients, scopes, or groups beyond the four named tiers plus
  oauth2-proxy. No abstractions for single-use resources.
- **Match existing style**: follow the `secrets.tf` idiom
  (`random_password` → `vault_kv_secret_v2` with `custom_metadata`
  `managed_by = "terraform"`). Keep the new `.tf` in the same root.
- Provider version is pinned to `5.3.0`
  (`.terraform.lock.hcl`); every resource/attribute used must exist in
  that version — verify against the `5.3.0` schema during
  implementation, do not assume newer attributes.

## 7. Code surface

New and touched files, all under `deployments/infrastructure/`:

- **NEW `deployments/infrastructure/oidc.tf`** — the whole OIDC stack:
  `vault_identity_oidc_key` (signing key; verify `allowed_client_ids`,
  `algorithm`, `rotation_period`, `verification_ttl` names against
  `5.3.0`), `vault_identity_oidc_scope` (name + `template` claim
  mapping), one `vault_identity_oidc_client` per RP (oauth2-proxy +
  three MinIO tiers; `redirect_uris`, `assignments`, `key`; exports
  `client_id` / `client_secret`), `vault_identity_oidc_assignment` per
  tier (`entity_ids` / `group_ids`), `vault_identity_oidc_provider`
  (ties `key` + scopes + `allowed_client_ids`; verify `issuer_host` /
  `https_enabled` attribute names). Also the `vault_identity_group`
  resources for the four tiers, and — conditional on Q1 — the
  entity/alias wiring.
- **`deployments/infrastructure/secrets.tf`** — add
  `vault_kv_secret_v2` entries writing each client's `client_id` /
  `client_secret` to `vault_mount.kvv2.path`, following the existing
  pattern at `secrets.tf:15-29`. (Author may keep these in `oidc.tf`
  instead; pick one and be consistent.)
- **`deployments/infrastructure/variables.tf:1-20`** — add variables
  for the redirect URIs / issuer host that depend on L1/M2 hostnames
  (see Q3, Q4), mirroring the existing simple `variable` blocks.
- **`deployments/infrastructure/vars/prod.tfvars`** and
  **`vars/prod.tfvars.example`** — supply values for any new variables.

Reference anchors the implementer will re-open: `providers.tf:7-10`,
`providers.tf:28`, `secrets.tf:2-7`, `secrets.tf:15-29`,
`services/haproxy.hcl:51-53`, `:64-66`, `:84-85`, `:91`,
`bootstrap/roles/vault_server/templates/vault.hcl.j2:7,17-20`.

## 8. Tests & validation gates

**Repo gate (the loop's gate):** `just pre_commit` →
`pre-commit run --all-files` (root `justfile:17-18`). The configured
hooks (`.pre-commit-config.yaml`) now validate Terraform. Alongside the
generic hooks (`check-json`, `check-ast`, `check-merge-conflict`,
`check-yaml`, `debug-statements`, `detect-private-key`,
`end-of-file-fixer`) and the local `nomad fmt` hook (`.hcl` only), two
local Terraform hooks run on every `.tf` change:

- `terraform-fmt` — `terraform fmt -check -recursive`
  (`.pre-commit-config.yaml:22-27`). Fails on unformatted `.tf`.
- `terraform-validate` — `scripts/tf_validate.sh`
  (`.pre-commit-config.yaml:28-33`), which runs `terraform validate`
  against each root (including `deployments/infrastructure/`) **offline**
  — `init -backend=false` pulls only provider schemas, so it never
  touches the Consul backend or live Vault. This is the cheapest catch
  for a wrong attribute/resource name against the pinned `5.3.0`
  provider.

So `just pre_commit` alone now covers `.tf` fmt + schema correctness;
the implementer does not need a separate manual `terraform validate`
step to satisfy the gate. **No hardcoded secret may appear in the diff**
(`detect-private-key` fails the gate, and the KV2 convention forbids it
regardless).

**Evals (live cluster).** The harness has live credentials in its
environment — `VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`,
`CONSUL_HTTP_ADDR` are all set — so the acceptance criteria are runnable
commands, not a manual operator step. `<provider>` below is the
`vault_identity_oidc_provider` name defined in `oidc.tf`; `<client>` is
a test/scratch client's name.

*Close-out acceptance target (run AFTER `terraform apply`).* These
require the feature to be applied to Vault; they are the bar the ticket
must clear at close, run once the operator has applied the plan against
the live cluster:

1. Discovery endpoint returns a valid config with an issuer and a
   `jwks_uri`:
   ```
   curl -sf -H "X-Vault-Token: $VAULT_TOKEN" \
     "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" \
     | jq -e '.issuer and .jwks_uri'
   ```
   Expected: exit 0, non-null `issuer` and `jwks_uri`.
2. The advertised JWKS is reachable and holds at least one key:
   ```
   JWKS=$(curl -sf -H "X-Vault-Token: $VAULT_TOKEN" \
     "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" \
     | jq -r '.jwks_uri')
   curl -sf "$JWKS" | jq -e '.keys | length > 0'
   ```
   Expected: exit 0, `keys` array non-empty.
3. A test client completes an authorization-code flow end to end
   against `<provider>` and `<client>` (authorize → code → token
   exchange), yielding an ID token whose group/entity claim (per Q5)
   carries the expected group. Expected: a signed ID token is returned
   and the group claim matches the client's assignment. This is the
   definitive functional check; it can only pass post-apply.

*Pre-apply guards (run WITHOUT apply, safe any time).* These confirm
the plan is well-formed before it reaches Vault and can run in the loop:

4. The gate passes: `just pre_commit` (fmt + offline `terraform
   validate` + secret scan) is green.
5. The resources are planned/created as expected. Before apply, confirm
   the graph with `terraform -chdir=deployments/infrastructure plan`
   (or `terraform state list` after apply) shows the
   `vault_identity_oidc_key`, `_scope`, `_client` (×4), `_assignment`
   (per tier), `_provider`, and the four `vault_identity_group`
   resources. Post-apply, the same objects can be read directly, e.g.
   `vault read identity/oidc/provider/<provider>` and
   `vault read identity/oidc/scope/<scope>` return the configured values.

Honest bound: evals 1–3 require the feature applied, so they are the
close-out acceptance target and are run after `terraform apply` against
the live cluster, not during loop iteration. The loop's own iteration
bar is eval 4 (the `just pre_commit` gate) plus eval 5's `plan`; the
apply-dependent evals 1–3 are recorded as the acceptance procedure to
execute at ticket close.

## 9. Risk assessment

- **Blast radius (loop-time):** near zero. F2 only adds Terraform files;
  it deploys nothing and the loop never applies. A wrong attribute name
  is caught by `terraform validate`, not in production.
- **Blast radius (apply-time, operator):** medium. This introduces the
  first identity/OIDC objects into a live Vault. A malformed
  `oidc_provider` or over-broad `allowed_client_ids` could expose an
  issuer that any client can use; assignments with empty/ wrong
  `group_ids` could let the wrong entities authenticate. Both are
  reviewable in `terraform plan` before apply.
- **Reversibility:** high. All resources are Terraform-managed and
  destroyable; no data migration, no job disruption. The signing key
  rotation is the only stateful concern (rotating it invalidates live
  tokens — not a concern pre-first-use).
- **Likeliest failure modes:** (1) attribute/resource name drift vs
  provider `5.3.0` (mitigate with `terraform validate`); (2) issuer
  served over plaintext HTTP being rejected by a downstream RP that
  demands an `https` issuer (see Q2); (3) redirect URIs guessed wrong
  because L1/M2 hostnames don't exist yet (see Q3/Q4) — these should be
  variables, not literals; (4) a `client_secret` accidentally committed
  (mitigated by KV2 convention + `detect-private-key`).

## 10. Subtickets (ordered, dependency-aware)

1. **Settle the forks.** Operator answers Q1 (human auth backend), Q2
   (http vs https issuer), Q3/Q4 (issuer host + redirect URIs). Blocks
   everything below that depends on them.
2. **Signing key + scope.** Add `vault_identity_oidc_key` and
   `vault_identity_oidc_scope` (group-claim template) to a new
   `oidc.tf`. Verify schema with `terraform validate`.
3. **Identity groups.** Add the four `vault_identity_group` resources
   (`minio-admins`, `minio-readers`, `minio-writers`,
   `dashboard-users`).
4. **Assignments + clients.** Add `vault_identity_oidc_assignment` per
   tier (referencing the groups) and one `vault_identity_oidc_client`
   per RP (oauth2-proxy + three MinIO tiers) with `redirect_uris` from
   variables; wire `allowed_client_ids` on the key.
5. **Provider.** Add `vault_identity_oidc_provider` tying key + scopes +
   clients into the issuer.
6. **Persist client secrets to KV2.** Add `vault_kv_secret_v2` entries
   (per `secrets.tf:15-29`) for each client's id/secret.
7. **Human enrollment (conditional on Q1).** If a backend is chosen,
   add the auth backend + `vault_identity_entity` / entity-alias /
   group-alias wiring so humans land in the right groups; otherwise
   document the prerequisite and leave group membership empty.
8. **Validate + document acceptance.** `terraform fmt`,
   `terraform validate`, `just pre_commit`; write the manual
   discovery/JWKS/auth-code acceptance steps into the ticket close-out.

## 11. Open questions (forks — operator must settle)

- **Q1 — Human auth backend (BLOCKING PREREQUISITE).** No human auth
  method exists today; only workload `jwt-nomad`
  (`bootstrap/roles/nomad_server/tasks/main.yml:198-255`). OIDC
  assignments gate on Vault *entities*, and entities only get populated
  by a human auth backend (userpass, OIDC-to-Google, LDAP). **Which
  backend, and where is it managed (this Terraform root vs bootstrap
  Ansible)?** *Recommendation:* for a single-operator home lab, enable a
  `userpass` auth backend managed in this same Terraform root, create
  `vault_identity_entity` per human + `vault_identity_entity_alias`, and
  add them to the groups via `member_entity_ids`. It is self-contained
  (no external IdP) and fully Terraform-expressible. Scaffold the groups
  and assignments now regardless; wire entities in subticket 7 once
  confirmed. (The operator email is a Google/gmail address, so
  OIDC-to-Google is a plausible alternative if federation is wanted —
  flag but do not choose.)

- **Q2 — HTTP vs HTTPS issuer.** Vault runs plaintext HTTP behind
  haproxy on port 80 (`vault.hcl.j2:17-20`, `haproxy.hcl:91`). The
  `vault_identity_oidc_provider` issuer will therefore be
  `http://vault.lab.orangecluster.nl/...` with `https_enabled = false`. Some OIDC
  relying parties (oauth2-proxy, MinIO) reject non-`https` issuers.
  *Recommendation:* ship `http` + `https_enabled = false` for v1 (works
  on the trusted LAN) and record that if L1/M2 report an
  https-issuer requirement, the fix is TLS termination at haproxy for
  `vault.lab.orangecluster.nl` — a separate ticket, not F2.

- **Q3 — Issuer host value.** Use the haproxy hostname
  `vault.lab.orangecluster.nl` (`haproxy.hcl:53`) or the direct backend IP
  `192.168.2.30:8200`? *Recommendation:* `vault.lab.orangecluster.nl`, so the
  issuer stays stable if the backend IP changes, and expose it as a
  variable with that default.

- **Q4 — Redirect URIs (L1/M2 hosts not built yet).** oauth2-proxy's
  landing-page host does not exist yet; the MinIO console is
  `minio.lab.orangecluster.nl` (`haproxy.hcl:84-85`) but its OIDC callback path is
  defined by M2. *Recommendation:* make every `redirect_uris` a
  Terraform variable (in `variables.tf` / `prod.tfvars`) with
  best-known placeholders (e.g. MinIO console
  `http://minio.lab.orangecluster.nl/oauth_callback`), so L1/M2 can set exact
  values without editing `oidc.tf`. Do not hardcode.

- **Q5 — Group-claim shape.** What claim key and value do the RPs read —
  a `groups` array of group names, or entity metadata? MinIO's OIDC
  policy claim and oauth2-proxy's `--oidc-groups-claim` must agree with
  the scope template. *Recommendation:* emit a `groups` claim listing
  the entity's Vault group names via the scope `template`, since that is
  what both MinIO and oauth2-proxy consume by default; confirm the exact
  template syntax against the `5.3.0` provider and Vault's
  identity-token templating.

- **Q6 — Secret placement / file split.** Keep the whole stack in one
  `oidc.tf`, and put client-secret KV2 writes there or in `secrets.tf`?
  *Recommendation:* single `oidc.tf` for the identity/OIDC resources;
  add the `vault_kv_secret_v2` client-secret writes in `secrets.tf`
  next to the existing credential blocks for discoverability. Either is
  fine; pick one for consistency.

**Eval marker.** These scenarios are encoded as the loop's Definition of
Done in `.loop/evals/F2-foundation-vault-oidc-provider.md` (validated by
`loopctl eval F2-foundation-vault-oidc-provider`).

## Resolved forks (operator, 2026-07-23)

- **Q1 → userpass in this Terraform root.** Enable a `userpass` auth
  backend managed in this same root; create `vault_identity_entity` per
  human + `vault_identity_entity_alias`, add to groups via
  `member_entity_ids`. Self-contained, no external IdP. (Google OIDC
  federation deferred as a future option, not chosen.)
- **Q2 → Require HTTPS now. DEPENDENCY: F2 is blocked on F3.** The OIDC
  issuer must be `https://vault.lab.orangecluster.nl/...` from day one — no
  plaintext OIDC. This requires TLS termination for `vault.lab.orangecluster.nl`
  at haproxy, which is F3's deliverable. **Build order becomes
  F1 → F3 → F2**; F2's eval cannot pass until F3 is merged. Set
  `https_enabled = true`.
- **Q3 → `vault.lab.orangecluster.nl` hostname.** Issuer uses the haproxy
  hostname (exposed as a variable with that default) so it stays stable
  across backend IP changes.
- **Q4 → Terraform variables + placeholders.** Every `redirect_uris` is
  a variable in `variables.tf`/`prod.tfvars` with best-known
  placeholders; L1/M2 set exact values without editing `oidc.tf`.
- **Q5 → `groups` array — as a service-agnostic contract.** Emit a
  single canonical `groups` claim (Vault group names) via the scope
  template. CONSTRAINT: this claim must generalize to every RP on
  localstack (oauth2-proxy for L1/R1/R4, MinIO M2, NATS R2, …), read
  identically by all — not a per-service shape. Confirm template syntax
  against the 5.3.0 provider.
- **Q6 → `oidc.tf` + `secrets.tf`.** Identity/OIDC resources in a single
  `oidc.tf`; `vault_kv_secret_v2` client-secret writes in `secrets.tf`
  beside the existing credential blocks.

**Cross-cutting (fed back from R1/R4, 2026-07-23):** the oauth2-proxy
architecture is **dedicated per service**, so F2 must provision one
`vault_identity_oidc_client` PER fronted service — `dash` (L1), `mlflow`
(R1), `phoenix` (R4) — each with its own `redirect_uris` variable and
KV2 secret, in addition to the MinIO-tier clients. Not a single shared
oauth2-proxy client.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: PARTIALLY SOUND. Gate verdict: `fail`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/F2-foundation-vault-oidc-provider.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: The client set is four different numbers: the body says 4, the plan's own addendum 6, the eval Definition of Done 5, and eval row 3 four. This decides what artifact exists at the end, and L1, R1, R4 and G1 all consume it.

This ticket is **`blocked`** (`unresolved-design-fork`). A1 applied no
structural fix here: the required fixes reverse design decisions or need an
operator call. **Do not implement from this plan as written.** Work the
verdict's required-fix list, then re-dispatch `loop-plan-reviewer` before
unblocking.
