---
epic = "foundation"
depends_on = ["T3-tls-edge-cutover-lab-domain", "A1-audit-plan-premise-sweep"]
priority = 50
summary = "Stand up the singleton half of Vault's OIDC identity provider in Terraform: signing key, scope, provider, the userpass human auth backend, and one smoke-test client proving a real login. Consumer clients belong to the tickets that consume them."
tags = ["vault", "oidc", "terraform"]
---

# F2 — Vault OIDC provider scaffolding (foundation)

**Rewritten 2026-07-30** against the thirteen required fixes in
`.loop/verdicts/F2-foundation-vault-oidc-provider.plan-validator.md` and two
operator decisions of the same date. The verdict is historical: it reviewed
the pre-rewrite plan. See "What changed in this rewrite" at the end.

## 1. Title

Stand up the parts of Vault's OIDC identity provider that are genuinely one
per cluster — signing key, scope, provider, and the human auth backend — plus
one throwaway client that proves a human can actually complete a login.
Consumer clients are NOT created here.

## 2. Size / Effort

**Small-to-medium**, smaller than the version this replaces. Six resource
types into an already-wired Terraform root with the Vault provider present.
Effort is (a) getting the `vault_identity_oidc_*` schema right against pinned
`5.3.0`, and (b) the userpass backend plus entity/alias wiring, which is new
ground in this repo.

## 3. Triggered by

Home-lab auth epic. Vault is the OIDC provider for humans; Zitadel was
evaluated and dropped. F2 is the keystone: every human OIDC login on the
cluster consumes this one issuer.

## 4. Context (verified live 2026-07-30)

Terraform root `deployments/infrastructure/`, Consul backend, applied with
`just apply`.

- **Provider pinned.** `providers.tf:7-10` pins `hashicorp/vault` `~>5.3.0`;
  `providers.tf:28` is an empty `provider "vault" {}` reading `VAULT_ADDR` /
  `VAULT_TOKEN` from the environment. Cite `providers.tf:7-10` as the pin.
  **Do not cite `.terraform.lock.hcl`**: it is gitignored
  (`deployments/.gitignore:2`) and absent from any worktree, and
  `scripts/tf_validate.sh` re-resolves `~>5.3.0` from the registry in a fresh
  worktree.
- **Vault resources that exist today.** More than a KV2 mount:
  `secrets.tf:2-7` (`vault_mount "kvv2"`), the `random_password` +
  `vault_kv_secret_v2` pattern at `secrets.tf:10-29`, `:47-66`, `:69-88`,
  plus `acme.tf:41` (`vault_policy`), `acme.tf:66`
  (`vault_jwt_auth_backend_role`), `consul_deploy_role.tf:19`,
  `nomad_deploy_role.tf:36`, and `backup.tf:34,50,65,81`. What is true is
  narrower: **no `vault_identity_*` resource exists in any Terraform root.**
- **No human auth backend.** `vault auth list` returns only `jwt-nomad/`
  (workload identity, built by `bootstrap/roles/nomad_server/tasks/main.yml:198-255`)
  and `token/`. No `userpass`, `oidc`, or `ldap`. F2 now creates it; see §5.
- **`identity/oidc/` is nearly greenfield, but NOT empty.** Read back
  2026-07-30:

  | Path | Live contents |
  | --- | --- |
  | `identity/oidc/key` | `default` (Vault built-in) |
  | `identity/oidc/scope` | **empty** — `No value found` |
  | `identity/oidc/client` | `test` |
  | `identity/oidc/assignment` | `allow_all` (built-in), `test` |
  | `identity/oidc/provider` | `default` (built-in) |

  The `test` client and `test` assignment are **unmanaged drift**: bound to a
  `Jasper Ginn` entity, in no `.tf` file. The client has empty
  `redirect_uris`, so it cannot complete a login flow and reads as leftover
  experimentation. The built-in `default` provider carries
  `allowed_client_ids = ["*"]`. See Q7.
- **Edge and issuer.** T1/T2/T3 shipped a publicly-trusted Let's Encrypt
  wildcard for `*.lab.orangecluster.nl`, and T3 superseded F3 and deleted its
  PKI. `https://vault.lab.orangecluster.nl` returns 200;
  `http://vault.lab.orangecluster.nl` **301s to https**. The Vault listener
  itself is still plaintext behind haproxy
  (`bootstrap/roles/vault_server/templates/vault.hcl.j2:7,17-20`), which is
  fine: TLS terminates at the edge and the issuer is the edge hostname.
- **haproxy anchors, re-opened 2026-07-30** (the pre-rewrite plan's six
  citations were all ~47 lines stale): Vault host ACL `haproxy.hcl:100`,
  routed by `:111` to backend `vault1 192.168.2.30:8200` at `:133-134`. MinIO
  console ACL `:98`, routed `:109`, backend `:127-128` to `192.168.2.29:9001`.

## 5. Non-goals / out of scope

- **Consumer OIDC clients.** F2 creates NO client for `dash` (L1), `mlflow`
  (R1), `phoenix` (R4), or the MinIO tiers (M2). Each consumer ticket creates
  its own `vault_identity_oidc_client`, its own group and assignment, and its
  own `vault_identity_oidc_key_allowed_client_id` entry. See "What changed".
- Not deploying any Nomad job, container, or service. Pure Terraform against
  the running Vault. No changes to `services.tf` or `services/*.hcl`.
- Not adding a Terraform provider; the Vault provider is present.
- Not configuring MinIO's OIDC settings or oauth2-proxy (M2, L1).
- Not terminating TLS or changing haproxy/listener config. T1/T2/T3 did that.

**Removed non-goal, 2026-07-30 (operator).** This section previously read
"Not standing up the human auth backend or enrolling real human users (see
Q1)". That contradicted the plan's own resolved Q1, which chose userpass in
this root. The operator settled it: **F2 stands up the backend.** Without it
nothing can log in, so F2 could not demonstrate its own issuer works, and
evals 4-5 would be unsatisfiable.

## 6. Requirements & restrictions

Must achieve:

1. **Signing key** (`vault_identity_oidc_key`) and **scope**
   (`vault_identity_oidc_scope`) with a claim template.
2. **Provider** (`vault_identity_oidc_provider`) whose issuer is
   `https://vault.lab.orangecluster.nl`, with `https_enabled = true`.
3. **A `userpass` auth backend** in this Terraform root, plus
   `vault_identity_entity` and `vault_identity_entity_alias` for the
   operator, so a real human identity exists and carries an `entity_id`.
4. **One smoke-test client**, its group, and its assignment — the minimum
   needed to prove an end-to-end authorization-code login. It is explicitly
   throwaway and may be deleted once a real consumer client exists.
5. **Consumers use F2's provider, never Vault's built-in `default`**
   (operator, 2026-07-30). Live, `identity/oidc/provider/default` advertises
   `allowed_client_ids = ["*"]` and an issuer of
   `http://192.168.2.30:8200/v1/identity/oidc/provider/default` — a raw IP
   over plain HTTP that accepts any client. It is a working issuer, so a
   consumer pointed at it by mistake would function, silently bypassing every
   scoping decision F2 makes. F2 must therefore (a) create a NAMED provider
   whose issuer is the HTTPS edge hostname, and (b) state in its close-out
   notes that each consumer's `config_url` / `--oidc-issuer-url` names F2's
   provider path, not `/default`. F2 does not delete or reconfigure
   `default`: it is Vault built-in and removing it is out of scope. See Q9.
6. **Client-id registration must not require editing the key resource.** Use
   `vault_identity_oidc_key_allowed_client_id` — **verified present in pinned
   5.3.0** by inspecting the provider binary — so each consumer ticket
   registers its own client without touching `oidc.tf`. Naming
   `allowed_client_ids` inline on the key creates a Terraform cycle with the
   client's `key` reference; that was the pre-rewrite plan's §10.4 defect.

Restrictions the repo enforces:

- **Secrets in Vault KV2, never hardcoded** (`AGENTS.md` Key Conventions;
  pattern `secrets.tf:15-29`). The smoke-test client's `client_secret` is
  written to `vault_mount.kvv2.path` via `vault_kv_secret_v2`.
  **Correction:** the pre-rewrite plan asserted three times that
  `detect-private-key` (`.pre-commit-config.yaml:12`) guards against a
  committed client secret. **It does not.** That hook matches a fixed
  blocklist of PEM headers only, and a Vault `hvo_secret_…` string is not one.
  The real guards are the KV2 convention, review, and eval row 6 below.
- **Surgical, minimum change** (`AGENTS.md` §2, §3). No speculative clients,
  scopes, or groups.
- **Match existing style:** `random_password` to `vault_kv_secret_v2` with
  `custom_metadata` `managed_by = "terraform"`.
- Provider pinned `~>5.3.0` at `providers.tf:7-10`. Every resource and
  attribute must exist in that version; `terraform validate` catches drift.

## 7. Code surface

All under `deployments/infrastructure/`:

- **NEW `oidc.tf`** — `vault_identity_oidc_key`, `vault_identity_oidc_scope`,
  `vault_identity_oidc_provider`, the smoke-test
  `vault_identity_oidc_client` + `vault_identity_group` +
  `vault_identity_oidc_assignment`, and the smoke-test's
  `vault_identity_oidc_key_allowed_client_id`.
- **NEW `auth_userpass.tf`** — `vault_auth_backend` (type `userpass`),
  `vault_generic_endpoint` or the userpass user resource, plus
  `vault_identity_entity` and `vault_identity_entity_alias` for the operator.
  Kept separate from `oidc.tf` because a later ticket may move human auth to
  a federated backend without touching the OIDC stack.
- **`secrets.tf`** — `vault_kv_secret_v2` for the smoke-test client's
  `client_id` / `client_secret`, beside the existing credential blocks.
- **`variables.tf`** / **`vars/prod.tfvars`** / **`vars/prod.tfvars.example`**
  — issuer host variable defaulting to `vault.lab.orangecluster.nl`, and the
  operator's userpass username. **No password in tfvars**; generate with
  `random_password` and write to KV2.

Anchors to re-open: `providers.tf:7-10`, `providers.tf:28`, `secrets.tf:2-7`,
`secrets.tf:15-29`, `services/haproxy.hcl:100`, `:111`, `:133-134`,
`bootstrap/roles/vault_server/templates/vault.hcl.j2:7,17-20`.

## 8. Tests & validation gates

**Repo gate:** `just pre_commit` (`justfile:18-19`) runs
`pre-commit run --all-files`. Terraform is covered by `terraform-fmt`
(`.pre-commit-config.yaml:22-27`) and `terraform-validate`
(`:28-33`, `scripts/tf_validate.sh`), the latter running `init -backend=false`
so it never touches the Consul backend or live Vault. That is the cheapest
catch for a wrong attribute name against 5.3.0.

**Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`)
before the first gate run, or `terraform-validate` dies on the gitignored
`.ssh/id_rsa` that `services.tf:290` reads.

### Evals

Authoritative set is `.loop/evals/F2-foundation-vault-oidc-provider.md`.

*Pre-apply, runnable in the loop:*

1. `just pre_commit` green.
2. **Count, do not grep.** After apply,
   `terraform -chdir=deployments/infrastructure state list | grep -c '^vault_identity'`
   equals the exact expected number, enumerated per-resource in the marker.
   The pre-rewrite eval grepped for presence, which passes against a partial
   stack.
3. **No client secret in the diff.** `git diff` over the branch matches no
   `client_secret\s*=\s*"` and no `hvo_secret_`. This replaces the
   `detect-private-key` claim, which cannot fail on this content.

*Post-apply, the close-out acceptance target:*

4. Discovery: `curl -sf "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" | jq -e '.issuer and .jwks_uri'`
   exits 0, and `.issuer` starts `https://vault.lab.orangecluster.nl`.
5. JWKS at the advertised `jwks_uri` returns a non-empty `keys` array.
6. **A real human login completes.** Authenticate to the new userpass backend
   as the operator, confirm the resulting token has a **non-empty
   `entity_id`**, then drive the authorization-code flow against the
   smoke-test client and exchange the code for an ID token whose group claim
   matches the assignment.

   **How rows 4-6 get an entity-bearing token, stated because the pre-rewrite
   plan did not:** the harness `$VAULT_TOKEN` is root and
   `vault token lookup` shows `entity_id: ""`, so it cannot exercise an
   entity-gated assignment. F2 creates the userpass backend, so the eval logs
   in with `vault login -method=userpass` using the generated password read
   from KV2. That token carries an entity. The advertised
   `authorization_endpoint` is a UI path, so the code exchange is driven
   against the `/v1/identity/oidc/provider/<provider>/authorize` API with an
   explicit `redirect_uri` matching the smoke-test client.

Honest bound: rows 4-6 need `terraform apply` against live Vault, which the
loop never performs. They are the close-out acceptance procedure, run by the
operator at apply time. The loop's own bar is rows 1-3.

## 9. Risk assessment

- **Loop-time blast radius: near zero.** F2 only adds Terraform. The loop does
  not apply.
- **Apply-time: medium.** First identity/OIDC objects in a live Vault, plus a
  new human auth backend. An over-broad assignment or a `userpass` user with
  a weak password is a real authentication surface. Review `terraform plan`
  before apply.
- **Reversibility: high.** All Terraform-managed and destroyable. Rotating the
  signing key invalidates live tokens, which is harmless before first use.
- **Likeliest failure modes:** (1) attribute drift vs 5.3.0, caught by
  `terraform validate`; (2) the `key` to `client` to `allowed_client_id`
  cycle, avoided by requirement 6; (3) a redirect URI mismatch on the
  smoke-test client, which surfaces as an opaque `invalid_redirect_uri`;
  (4) adopting rather than replacing the drifting `test` client, see Q7.

## 10. Subtickets (ordered)

1. **Signing key + scope** in `oidc.tf`. `terraform validate`.
2. **Userpass backend + operator entity and alias** in `auth_userpass.tf`,
   password via `random_password` written to KV2.
3. **Provider**, issuer `https://vault.lab.orangecluster.nl`,
   `https_enabled = true`.
4. **Smoke-test group, assignment, client, and its
   `vault_identity_oidc_key_allowed_client_id`.**
5. **Persist the smoke-test client id/secret to KV2** per `secrets.tf:15-29`.
6. **Gate:** `just worktree_setup`, then `just pre_commit`.
7. **Write the close-out acceptance procedure** into the ticket (below).

## Close-out procedure (operator, at apply time)

The loop commits the Terraform. It does not apply it. After `just apply` in
`deployments/infrastructure`:

1. **Run the post-apply eval rows** from
   `.loop/evals/F2-foundation-vault-oidc-provider.md` — marker rows 1, 2, 4, 5
   and 6 (the plan's §8 numbering differs; go by the marker): discovery over
   HTTPS with the issuer prefix asserted, JWKS non-empty, a real `userpass`
   login yielding a NON-empty `entity_id`, the authorization-code flow
   carrying the `groups` claim, then the non-member denial.

   **Row 6 needs a second entity, and F2 does not create one.** Make a
   throwaway that is deliberately NOT in `oidc-smoke`, run the same
   authorization request as row 5, confirm it is refused, then delete it:
   ```
   vault write auth/userpass/users/rowsix password="$(openssl rand -base64 24)"
   vault write identity/entity name=rowsix
   vault write identity/entity-alias name=rowsix \
     canonical_id=$(vault read -field=id identity/entity/name/rowsix) \
     mount_accessor=$(vault auth list -format=json | jq -r '."userpass/".accessor')
   # log in as rowsix, drive /authorize against the smoke client: expect DENIED
   vault delete identity/entity/name/rowsix
   vault delete auth/userpass/users/rowsix
   ```
   Without this, row 5 passing proves only that login works, not that the
   assignment gates anything, which is the property the row exists for.

   **The authorize request MUST ask for the groups scope**, or none of the
   above proves anything. Vault's `/identity/oidc/provider/<name>/authorize`
   takes a space-delimited `scope` and only `openid` is required, so a request
   sending `scope=openid` returns a signed `id_token` with no `groups` claim
   even when the scope template is perfect. Send:
   ```
   scope=openid groups
   ```
   alongside the other authorize params (`client_id`, `redirect_uri`,
   `response_type=code`, `state`, `nonce`).

   **Then check the claim is actually present, not just that a token came
   back.** Decode the `id_token` payload and assert `groups` exists and is an
   ARRAY. A malformed scope template makes Vault drop the claim silently and
   still return a signed token, so "the flow completed" is not evidence. This
   is the exact trap that hid the `jsonencode` defect: apply succeeded, tokens
   issued, and the claim was simply absent.
2. **Delete the drifting `test` OIDC client and its assignment**, per Q7. This
   is not a Terraform resource: F2 cannot express deleting an object it does
   not manage, so it is a manual step.
   ```
   vault delete identity/oidc/client/test
   vault delete identity/oidc/assignment/test
   ```
   **Leave alone** the built-in `default` provider, the `default` key, and the
   `allow_all` assignment. Those are Vault's own, not drift.
3. **Confirm the result:** `vault list identity/oidc/client` returns only the
   smoke-test client, and `vault list identity/oidc/assignment` returns
   `allow_all` plus the smoke-test assignment.
4. Record in the ticket close-out which of steps 1-3 ran and what they
   returned, so eval row 11 can be scored against something.

## 11. Open questions

- **Q7 → RESOLVED (operator, 2026-07-30): delete `test` and its assignment.**
  Both exist in live Vault, are Terraform-unmanaged, and the client's secret
  was exposed in plaintext during A1's audit on 2026-07-30. Its
  `redirect_uris` is empty, so it cannot complete a login and reads as
  leftover experimentation. The operator chose deletion over import: it
  removes the drift and the exposed secret in one step, and F2's own
  smoke-test client becomes the managed one. Importing was rejected because
  it pins F2 to an artifact nobody designed and keeps a known-exposed
  credential alive.
  **This is an apply-time action, not a Terraform resource.** F2 cannot
  express "delete an object I do not manage". Do it as an explicit close-out
  step alongside the apply: `vault delete identity/oidc/client/test` then
  `vault delete identity/oidc/assignment/test`. Record it in the close-out
  notes so eval row 11 can score it. Leave the built-in `default` provider,
  `default` key and `allow_all` assignment alone; those are Vault's own.

- **Q9 — Should the built-in `default` provider be locked down?** It
  advertises `allowed_client_ids = ["*"]`, so any client that names it gets a
  working issuer, bypassing F2's scoping. F2 creates a named provider and
  documents that consumers must use it (requirement 5), but nothing stops a
  future misconfiguration from pointing at `/default` and appearing to work.
  *Recommendation:* leave `default` alone in F2 (it is Vault built-in and
  altering it is a separate blast radius), and instead have each consumer
  ticket's eval assert its issuer URL matches F2's provider path. Raise a
  follow-up if the operator wants `default` restricted cluster-wide.

- **Q8 — Does the `groups` claim generalize, or is it per-RP?** The
  pre-rewrite plan's resolved Q5 required one canonical `groups` claim "read
  identically by all" RPs. That is now known to be false for at least one
  consumer: M2 tiers MinIO on `role_policy`, which **bypasses the claim
  entirely**, with Vault's per-client assignment doing the gating
  (`.loop/plans/M2-minio-poc-human-tiers.md:92-95`, `:113-114`).
  *Recommendation:* keep emitting a `groups` claim in the shared scope, but
  drop "read identically by all" and scope the requirement to the RPs that
  genuinely consume it (oauth2-proxy for L1/R1/R4). Each consumer ticket
  states whether it reads the claim or gates on assignment.

## Resolved forks

**Operator, 2026-07-23** (still standing unless noted):

- **Q1 → userpass in this Terraform root.** Now a requirement, not a
  conditional; see §5 and §6.3.
- **Q2 → require HTTPS. `https_enabled = true`.** *Dependency prose refreshed
  2026-07-30:* the original text said "F2 is blocked on F3" and set build
  order "F1 → F3 → F2". That no longer describes the ledger. TLS for
  `vault.lab.orangecluster.nl` was delivered by T1+T3; T3 superseded F3 and
  deleted its PKI; F3, T1, T2 and T3 are all `done`. F1 is still `ready` and
  is **not** required by F2 — F1 concerns Nomad workload identity, which F2
  does not touch.
- **Q3 → `vault.lab.orangecluster.nl`** as the issuer host, via a variable
  with that default.
- **Q4 → redirect URIs are variables**, never literals. Applies to the
  smoke-test client here; consumer tickets own theirs.
- **Q5 → superseded by Q8 above.**
- **Q6 → `oidc.tf` + `secrets.tf`**, with `auth_userpass.tf` added by this
  rewrite.

**Operator, 2026-07-30:**

- **F2 shrinks to the singleton pieces.** F2 owns the key, scope, provider,
  userpass backend, operator entity, and one smoke-test client. It creates no
  consumer clients. The cross-cutting note fed back from R1/R4 on 2026-07-23,
  which required "one `vault_identity_oidc_client` PER fronted service" in
  F2, is **superseded**: that requirement is now discharged by each consumer
  ticket. Rationale: a client is per-consumer, nothing makes it shared,
  centralizing made F2 a bottleneck and produced four contradictory client
  counts across §6, §10.4, the addendum and the eval marker. The usual reason
  to centralize — the key's `allowed_client_ids` list — does not apply,
  because 5.3.0 ships `vault_identity_oidc_key_allowed_client_id` as a
  standalone resource.
- **The human auth backend is in scope**, and its non-goal is deleted.

## What changed in this rewrite

Against `.loop/verdicts/F2-foundation-vault-oidc-provider.plan-validator.md`
(premise PARTIALLY SOUND, gate `fail`, thirteen required fixes):

- Fixes 1 and 10 **dissolved** by the scope shrink: there is no client count
  to reconcile, and no key-to-client cycle to solve.
- Fix 2 applied: the §5 non-goal is deleted and Q1's resolution is now a
  requirement.
- Fix 3 applied: all six `haproxy.hcl` anchors re-opened and rewritten.
- Fixes 4 and 5 applied: the `detect-private-key` guarantee is deleted and
  named as false; eval rows now count and pattern-match the diff.
- Fix 6 applied: §8 states exactly how an entity-bearing token is obtained.
- Fixes 7, 8, 9 applied: §4's Vault-resource inventory, the HTTP/HTTPS prose,
  and the lockfile citations corrected.
- Fix 11 applied as Q8. Fix 12 applied as the drift table in §4 plus Q7.
  Fix 13 applied in the Q2 note.

Two corrections to the verdict itself, verified live 2026-07-30: it reported
one drifting assignment, but there are **two** (`allow_all` and `test`); and
`identity/oidc/scope` is **empty**, which it did not state.
