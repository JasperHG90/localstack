---
epic = "foundation"
depends_on = ["F2-foundation-vault-oidc-provider", "A1-audit-plan-premise-sweep"]
priority = 45
summary = "Replace the Terraform deployer's static Vault root token with an operator OIDC login, and author a scoped deployer policy granting exactly the KV2, nomad/creds, consul/creds, and database/creds paths it needs."
tags = ["vault", "oidc", "terraform", "policy"]
---

# F7 — Deployer Vault OIDC login + scoped `deployer` policy (foundation)

## 1. Title

Replace the Terraform deployer's static Vault **root token** with an
operator **OIDC login** (`vault login -method=oidc`, reusing the F2
OIDC identity provider) and author a scoped **`deployer` Vault policy**
that grants exactly the KV2 paths, `nomad/creds/deploy`,
`consul/creds/deploy`, and `database/creds/*` the deployer needs — never
root-equivalent.

## 2. Size / Effort

**Medium.** The Terraform resource graph is small: one `vault_policy`
(the `deployer` policy) plus the operator OIDC auth wiring (auth backend
+ role + role-to-policy binding). Effort is driven by (a) the
auth-method fork — F2 stood up an OIDC *provider* (an IdP for downstream
RPs), not a Vault *login* auth method, so the exact login mechanism has a
genuine fork (Q1); (b) enumerating every KV2 path the deployer writes
today so the policy is neither too narrow (breaks the next `apply`) nor
root-equivalent; and (c) the policy references paths F5/F6 create
(`nomad/creds/deploy`, `consul/creds/deploy`) that do not exist yet, so
the policy is authorable now but only fully exercisable once F5/F6 land.

## 3. Triggered by

Home-lab auth epic, F5–F8 sub-feature (the privileged deployer). Vault is
the confirmed identity root (F1 = Nomad workload JWT trust; F2 = human
OIDC provider). The existing tickets cover humans and in-cluster
workloads but **not** the privileged Terraform deployer (this repo),
which today authenticates to Vault with the **static Vault root token**
seeded into `.devcontainer/.env`. F7 establishes the deployer's
authentication front door (operator OIDC login) and its scoped policy;
F5 (Nomad secrets engine) and F6 (Consul secrets engine) supply the
brokered child creds the policy grants read on; F8 does the provider
cutover that drops the env-var token.

## 4. Context

Today's state — the deployer authenticates to Vault as **root**:

- Both Terraform roots declare an **empty** Vault provider that reads
  `VAULT_ADDR` / `VAULT_TOKEN` from the environment:
  `deployments/applications/providers.tf:32` (`provider "vault" {}`, and
  the `hashicorp/vault ~>5.3.0` pin at `:7-10`) and
  `deployments/infrastructure/providers.tf:28` (same empty block, pin at
  `:7-10`). Neither passes a token literal — the value comes from the
  shell env.
- That env `VAULT_TOKEN` is the Vault **root token**. The devcontainer
  env template seeds `VAULT_TOKEN=` (`.devcontainer/.env.example`, Vault
  credentials block), and bootstrap reads the stored root token from
  `/opt/vault/init.json` and uses it for every Vault write:
  `bootstrap/roles/nomad_server/tasks/main.yml:189-196` slurps the file
  and sets `vault_bootstrap_token` from `.root_token`, then passes it as
  `VAULT_TOKEN` on every subsequent `vault` command (e.g. `:202`,
  `:211`, `:224`, `:241`). The operator copies this same token into
  `.devcontainer/.env` for local `terraform apply`. So the deployer runs
  with unrestricted root capability today.
- The KV2 mount the deployer manages is `vault_mount "kvv2"` at
  `deployments/infrastructure/secrets.tf:2-7`, path = `var.secret_mount`
  (a required variable, no default:
  `deployments/infrastructure/variables.tf:1-4`;
  `deployments/applications/variables.tf:1`). The deployer writes these
  KV2 secret names under it, all prefixed `default/`:
  - **infrastructure root** (`secrets.tf`): `default/minio/localstack`
    (`:15-29`), `default/openfang/basic_auth` (`:37-44`),
    `default/grafana/admin` (`:52-66`), `default/postgres/localstack`
    (`:74-88`).
  - **applications root** (`secrets.tf`): `default/postgres/<role>`
    (`:1-9`, `for_each`), `default/phoenix/postgres` (`:11-18`),
    `default/memex/postgres` (`:22-29`), `default/memex/minio`
    (`:31-38`), `default/loki/minio` (`:42-49`), `default/mlflow/postgres`
    (`:53-60`), `default/mlflow/minio` (`:62-69`), `default/memex/auth`
    (`:79-86`), `default/hermes/api_server` (`:94-100`),
    `default/minio/<user>` (`:102-110`, `for_each`).
  A KV2 v2 mount splits every logical path into `<mount>/data/<name>`
  (read/write) and `<mount>/metadata/<name>` (list/delete). The policy
  must cover both sub-paths. The precedent for this KV2 split is the
  Nomad-workload policy template (`secret/data/...` and
  `secret/metadata/...` at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-15`).
- **F2's OIDC scaffolding is an identity *provider* (IdP), not a login
  auth method.** F2 stands up `vault_identity_oidc_*` resources so
  downstream relying parties (MinIO console, oauth2-proxy) can
  authenticate humans against Vault as the issuer
  (`.loop/plans/F2-foundation-vault-oidc-provider.md:87-102`). F2's
  *resolved* human-login backend is **userpass**, not an `oidc` login
  method (F2 Resolved Q1,
  `.loop/plans/F2-foundation-vault-oidc-provider.md:351-356`). For the
  operator to run `vault login -method=oidc`, Vault needs an **`oidc`
  auth method** (an `vault_jwt_auth_backend` in `oidc` mode + a
  `vault_jwt_auth_backend_role`) pointed at an OIDC issuer. This gap is
  the load-bearing fork (Q1).
- **Policy management precedent.** Vault policies today are created two
  ways: Ansible at bootstrap (`vault policy`-style writes via the
  nomad_server role) and, for later foundation work, Terraform
  `vault_policy` (the F3 resolved fork chose a dedicated `vault_policy`
  resource, `.loop/plans/F3-foundation-haproxy-tls-vault-pki.md`
  Resolved Q1). The scoped Nomad-workload policy is templated at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  and shows the repo's scoped-policy shape (explicit `path` blocks with
  minimal `capabilities`, never a `path "*"` wildcard).
- The brokered child-cred paths the policy will grant `read` on do not
  exist yet: `nomad/creds/deploy` (F5) and `consul/creds/deploy` (F6)
  have **no ticket authored** (`.loop/plans/` has no F5/F6/F8 file).
  The database-creds path **does** have precedent: S2/R3 introduce a
  `database/` secrets mount with `database/creds/<role>` dynamic roles
  (`.loop/plans/R3-rollout-postgres-vault-db-creds.md:148,168,175`;
  `.loop/plans/S2-spike-postgres-vault-creds.md:74,170,175`).

What is missing: (1) an operator login front door to Vault that is not
the root token, and (2) a scoped `deployer` policy that grants exactly
the paths above and nothing more.

## 5. Non-goals / out of scope

- **Not** the Nomad or Consul secrets engines themselves. F5 adds the
  `nomad/` engine + `nomad/creds/deploy`; F6 adds the `consul/` engine +
  `consul/creds/deploy`. F7 only *references* those paths in the policy.
- **Not** the provider cutover. F8
  (`F8-foundation-deployer-provider-cutover`) is the ticket that repoints
  `provider "vault" {}` to the OIDC-derived token and removes
  `VAULT_TOKEN=` (root) from `.devcontainer/.env`. F7 stands up the
  login mechanism and the policy; it does not force the deployer to stop
  using the root token.
- **Not** CI / GitHub-Actions auth. The GitHub-Actions-OIDC → Vault-JWT
  keyless path is explicitly **deferred** to a later ticket. F7 is
  operator-run only. Record it as a one-line future-work note; do not
  design it here.
- **Not** redesigning F2's OIDC provider. Consume the existing issuer;
  do not add or alter `vault_identity_oidc_*` resources.
- **Not** rotating or revoking the existing root token, or changing how
  bootstrap uses it (`nomad_server/tasks/main.yml` keeps using the root
  token for first-boot bootstrap — that is a chicken-and-egg necessity,
  out of scope here).

## 6. Requirements & restrictions

Must achieve:

1. An operator can obtain a Vault token by human identity, not the root
   token: `vault login -method=oidc` (reusing the F2 OIDC provider as
   the issuer) yields a token bound to the **`deployer`** policy. The
   exact auth-method wiring depends on Q1.
2. A scoped **`deployer` Vault policy** (a `vault_policy` resource,
   authored in Terraform following the F3 precedent) granting **exactly**:
   - `read`/`create`/`update` on the KV2 data paths for every
     `default/*` secret the deployer manages (both `<mount>/data/*` and
     `<mount>/metadata/*` — see §4 enumeration), scoped to the
     `default/` prefix under `var.secret_mount`, NOT the whole mount root
     and NOT `sys/*`.
   - `read` on `nomad/creds/deploy` (F5).
   - `read` on `consul/creds/deploy` (F6).
   - `read` on `database/creds/*` (S2/R3 — the deployer may need to mint
     DB users during `apply`; confirm scope in Q3).
   The policy MUST NOT be root-equivalent: no `path "*"`, no `sys/*`
   management capability, no `auth/*` or `identity/*` write. An
   out-of-scope path (e.g. a `sys/policies` write, or a KV path outside
   `default/`) must be **denied** to a `deployer`-token holder.
3. The operator's Vault OIDC token TTL is sane for a deploy session (Q2);
   the child creds it brokers (Nomad/Consul/DB) are short-lived +
   auto-renewing, owned by F5/F6/R3 — F7 does not set their TTLs.

Restrictions the repo enforces (cite where stated):

- **Secrets live in Vault KV2, never hardcoded** (`CLAUDE.md` Key
  Conventions; `.pre-commit-config.yaml` `detect-private-key`). The OIDC
  auth method's `client_secret` (if the chosen mechanism needs one) must
  be written to the KV2 mount following the `vault_kv_secret_v2` idiom at
  `secrets.tf:15-29`, never committed.
- **Surgical, minimum change** (`CLAUDE.md` §2, §3): one `deployer`
  policy, one auth-method wiring. No speculative extra roles, no
  broadening of adjacent policies, no refactor of the existing
  `secrets.tf` blocks.
- **Match existing style**: scoped `path` blocks with minimal
  `capabilities`, modeled on
  `vault_nomad_workloads.hcl.j2:1-24`; `vault_policy` +
  `vault_jwt_auth_backend_role` shape modeled on F3's resolved approach.
- **Least privilege** is the explicit contract of this ticket: the
  policy is the deliverable's whole point, so the "not root-equivalent"
  guardrail (§8 eval) is a hard requirement, not a nice-to-have.
- Provider is pinned to `5.3.0` (`providers.tf:7-10`,
  `.terraform.lock.hcl`); every resource/attribute must resolve against
  that schema — offline `terraform validate` catches drift.

## 7. Code surface

All new/touched files under `deployments/infrastructure/` (this is the
root where Vault auth/policy foundation lives, matching F2/F3):

- **NEW `deployments/infrastructure/deployer.tf`** — the whole F7 stack:
  - `vault_policy "deployer"` — the scoped policy (§6 req 2). Enumerate
    explicit `path` blocks for each `default/*` KV2 data + metadata
    prefix, the three creds reads, and nothing else. No wildcard root.
  - The operator OIDC auth wiring (shape depends on Q1): most likely a
    `vault_jwt_auth_backend` in `type = "oidc"` mode plus a
    `vault_jwt_auth_backend_role` (`role_type = "oidc"`,
    `token_policies = ["deployer"]`, `allowed_redirect_uris`,
    `oidc_scopes`), pointed at the F2 issuer. If a separate
    `client_secret` is generated, add its `vault_kv_secret_v2` write here
    or in `secrets.tf` (pick one; be consistent with F2 Resolved Q6).
- **`deployments/infrastructure/variables.tf:1-4`** — add variables for
  any OIDC-auth inputs that vary by environment (issuer host / discovery
  URL, redirect URI, TTLs from Q2), mirroring the existing simple
  `variable` blocks. Do not hardcode the issuer host.
- **`deployments/infrastructure/vars/prod.tfvars`** and
  **`vars/prod.tfvars.example`** — supply values for any new variables.
- **NEW `docs/` runbook (optional, per Q4)** — a short operator runbook:
  `vault login -method=oidc` then `terraform apply`. If added, it is a
  markdown doc and MUST pass the slop scan (`.claude/rules/slop-scan-for-docs.md`).

Reference anchors the implementer will re-open (do not edit unless the
clause says so): `providers.tf:28` and `:32` (empty vault provider — F8
edits these, not F7), `secrets.tf:2-7,15-29` (KV2 mount + write idiom),
`vault_nomad_workloads.hcl.j2:1-24` (scoped-policy shape),
`nomad_server/tasks/main.yml:189-196` (root-token source — read-only
context).

## 8. Tests & validation gates

**Repo gate (the loop's gate):** `just pre_commit` →
`pre-commit run --all-files` (root `justfile:16-18`,
`.loop/config.json` `gates`). The configured hooks
(`.pre-commit-config.yaml`) validate Terraform: alongside the generic
hooks (`check-json`, `check-ast`, `check-merge-conflict`, `check-yaml`,
`debug-statements`, `detect-private-key`, `end-of-file-fixer`) and the
`nomad fmt` hook (`.hcl` only), two local Terraform hooks run on every
`.tf` change:

- `terraform-fmt` — `terraform fmt -check -recursive`
  (`.pre-commit-config.yaml`, `terraform-fmt` hook).
- `terraform-validate` — `scripts/tf_validate.sh` (validates each root
  **offline** via `init -backend=false`, incl.
  `deployments/infrastructure/`), the cheapest catch for a wrong
  attribute/resource name against the pinned `5.3.0` provider.

So `just pre_commit` alone covers `.tf` fmt + schema correctness. No
hardcoded secret may appear in the diff (`detect-private-key` + the KV2
convention). If a runbook doc is added, run the slop scan
(`.claude/rules/slop-scan-for-docs.md`) before declaring done.

**Live-cluster evals.** The harness env has `VAULT_ADDR` / `VAULT_TOKEN`
set, so the acceptance checks are runnable commands. `<policy>` is
`deployer`.

*Close-out acceptance target (run AFTER `terraform apply`):*

1. **The `deployer` policy exists and lists exactly its scoped paths.**
   `vault policy read deployer` returns the KV2 `default/*` data +
   metadata blocks, `nomad/creds/deploy`, `consul/creds/deploy`,
   `database/creds/*` — and NO `path "*"`, NO `sys/*` write, NO
   `identity/*`/`auth/*` write. Expected: policy present, wildcard-root
   absent.
2. **A `deployer`-scoped token can read/write the KV2 paths it manages.**
   With a token minted under the `deployer` policy, `vault kv get
   <mount>/default/minio/localstack` and a `vault kv put` to a
   `default/*` test path both succeed. Expected: exit 0.
3. **The guardrail: an out-of-scope path is DENIED to a `deployer`
   token.** With the same token, `vault write sys/policies/acl/xyz
   policy=-` (or `vault kv get <mount>/notdefault/x`, or `vault token
   create -policy=root`) returns **403 / permission denied**. Expected:
   denied, proving the policy is not root-equivalent. **This is the
   definitive least-privilege check.**
4. **Operator OIDC login yields a `deployer` token.** `vault login
   -method=oidc` (against the F2 issuer, per Q1) completes and the
   resulting token's `token_policies` include `deployer` and do NOT
   include `root`. Expected: login succeeds, policy binding correct.
   (Depends on F2 landing — see Q1/Risk.)

*Pre-apply guards (run WITHOUT apply, safe any time, this is the loop's
iteration bar):*

5. `just pre_commit` is green (fmt + offline `terraform validate` +
   secret scan).
6. `terraform -chdir=deployments/infrastructure plan` shows the
   `vault_policy.deployer` and the OIDC auth-backend/role resources
   planned, with no `client_secret` literal in the diff.

Honest bound: evals 1–4 require the feature applied to live Vault (and
eval 4 additionally requires F2 merged), so they are the close-out
acceptance target, run after `terraform apply`. The loop's own iteration
bar is evals 5–6.

Every named test/check above has its file home in §7 (`deployer.tf`,
`variables.tf`, `vars/prod.tfvars*`); no check references a file not in
the code surface.

## 9. Risk assessment

- **Blast radius (loop-time):** near zero. F7 adds Terraform files; the
  loop never applies. A wrong attribute is caught by `terraform
  validate`.
- **Blast radius (apply-time, operator):** medium-high — this is a
  *privileged-access* policy. An over-broad `deployer` policy (a stray
  `sys/*` or `path "*"`) silently re-creates the root-equivalence this
  ticket exists to remove; eval 3 is the guard. An under-broad policy
  breaks the very next `terraform apply` (the deployer can no longer
  write a KV2 secret it manages); the §4 path enumeration + eval 2 guard
  that.
- **Reversibility:** high. `vault_policy` and the auth backend/role are
  Terraform-managed and destroyable; the root token still works until F8
  removes it, so a broken `deployer` policy cannot lock the operator out
  (they fall back to the root token).
- **Likeliest failure modes:** (1) **the auth-method fork (Q1)** — F2
  provides an OIDC *provider*, not an OIDC *login* method; if the
  implementer assumes `vault login -method=oidc` "just works" off F2
  without adding a `vault_jwt_auth_backend` in `oidc` mode, the login
  fails. (2) KV2 v2 path split forgotten (`data/` granted,
  `metadata/` not, or vice-versa) — breaks list/delete or read.
  (3) Policy references `nomad/creds/deploy` / `consul/creds/deploy`
  before F5/F6 create them — the *policy* still applies (Vault policies
  need no backing path to exist), but eval 4's brokered read can't be
  exercised until F5/F6 land. (4) An issuer served over plaintext being
  rejected — but F2 Resolved Q2 already requires an **https** issuer via
  F3, so this is inherited, not new here.

## 10. Subtickets (ordered, dependency-aware)

1. **Settle the forks.** Operator answers Q1 (OIDC login mechanism vs
   AppRole fallback), Q2 (token TTL), Q3 (`database/creds/*` breadth),
   Q4 (runbook doc). Q1 blocks the auth-method half; the policy half can
   proceed regardless.
2. **Author the `deployer` policy.** Add `vault_policy "deployer"` to a
   new `deployer.tf`, enumerating every `default/*` KV2 data + metadata
   path (§4) plus the three creds reads, modeled on
   `vault_nomad_workloads.hcl.j2`. Verify with `terraform validate`.
   This is the core deliverable and is independent of F2/F5/F6.
3. **Wire the operator OIDC login (depends on Q1 + F2).** Add the
   `vault_jwt_auth_backend` (`oidc`) + `vault_jwt_auth_backend_role`
   binding `token_policies = ["deployer"]`, pointed at the F2 issuer.
   Persist any `client_secret` to KV2. If F2 has not landed, stub the
   AppRole fallback per Q1 and flag.
4. **Variables + tfvars.** Add issuer/redirect/TTL variables to
   `variables.tf` and values to `vars/prod.tfvars(.example)`.
5. **Validate + document acceptance.** `terraform fmt`, `terraform
   validate`, `just pre_commit`; write the runbook (Q4) if chosen and
   slop-scan it; record the post-apply acceptance steps (evals 1–4).

## 11. Open questions (forks — operator must settle)

- **Q1 — The OIDC login mechanism (LOAD-BEARING).** The directive says
  "reuse the F2 OIDC provider for `vault login -method=oidc`", but F2
  stands up an OIDC *identity provider* (an IdP serving downstream RPs
  like MinIO/oauth2-proxy), and F2's *human* login backend resolved to
  **userpass**, not an `oidc` login method
  (`F2-foundation-vault-oidc-provider.md:351-356`). `vault login
  -method=oidc` needs a Vault **`oidc` auth method**
  (`vault_jwt_auth_backend` in `oidc` mode + role) pointed at *some*
  OIDC issuer. *Recommendation:* enable an `oidc` auth backend in this
  root pointed at the operator's real IdP — the operator email is a
  Google/gmail address, so **OIDC-to-Google** is the natural issuer
  (Google is already a declared provider in the infra root,
  `providers.tf:15-18,30-32`), binding the role to
  `token_policies = ["deployer"]`. Reusing F2's *Vault-hosted* issuer
  for Vault's own login is circular (Vault can't be its own upstream IdP
  for a login method), so "reuse F2" most sensibly means "reuse the same
  human-identity source / group model", not "point Vault at itself".
  Confirm the intended issuer. **AppRole is the fallback only if F2/the
  IdP slips** — do not make it the primary path.
- **Q2 — Operator token TTL.** What `token_ttl` / `token_max_ttl` for the
  deployer login role? *Recommendation:* a deploy-session-sized TTL —
  `token_ttl = 1h`, `token_max_ttl = 8h` (renewable within a working
  session, expires overnight). The brokered child creds (Nomad/Consul/DB)
  are short-lived + auto-renewing and are F5/F6/R3's concern, not this
  role's.
- **Q3 — `database/creds/*` breadth in the policy.** Grant the deployer
  `read` on all `database/creds/*` roles, or only the specific roles it
  provisions during `apply`? S2/R3 flag the same scope question for the
  *workload* policy (`S2-spike-postgres-vault-creds.md:359`).
  *Recommendation:* `database/creds/*` for the deployer (it is the
  privileged actor that creates the roles, so it legitimately manages all
  of them), while workload policies stay per-role. Confirm this does not
  overlap awkwardly once R3 lands.
- **Q4 — Runbook doc.** Ship a short operator runbook (`vault login
  -method=oidc` then `terraform apply`), or leave it to F8's cutover?
  *Recommendation:* a minimal runbook here is cheap and de-risks the
  hand-off, but F8 owns the actual "drop the root token" story, so a
  one-paragraph note in this ticket's close-out may suffice. Author the
  doc only if the operator wants a standalone runbook; if so it must pass
  the slop scan.
- **Q5 — Where the auth method + policy are managed.** This root
  (`deployments/infrastructure/`, matching F2/F3) vs bootstrap Ansible
  (where the root token and `jwt-nomad` live)? *Recommendation:*
  Terraform in `deployments/infrastructure/`, consistent with F2/F3's
  resolved choice to keep Vault identity/policy foundation in Terraform,
  not Ansible. Bootstrap keeps only the unavoidable first-boot root-token
  use.

**Future work (deferred, one line):** GitHub-Actions-OIDC → Vault-JWT
keyless CI auth for the deployer is explicitly out of scope and deferred
to a later ticket.

**Cross-refs / dependencies:**
- **F7 DEPENDS ON F2** (`F2-foundation-vault-oidc-provider`) for the
  OIDC identity source. Recommend pulling F2 forward (note: F2 itself is
  blocked on F3 for its https issuer, so the effective order is
  F1 → F3 → F2 → F7). The `deployer` *policy* half can be authored and
  merged ahead of F2; only the login-method half needs F2.
- The `deployer` policy **references** `nomad/creds/deploy` (F5) and
  `consul/creds/deploy` (F6). The policy is authorable now (Vault
  policies do not require the backing path to exist), but eval 4's
  brokered-read is only meaningful once F5/F6 land.
- **F8** (`F8-foundation-deployer-provider-cutover`) DEPENDS ON F7: F8
  repoints `provider "vault" {}` at the OIDC-derived token and removes
  the root `VAULT_TOKEN` from `.devcontainer/.env`.

**Eval marker.** These scenarios are the loop's Definition of Done and
must be encoded in `.loop/evals/F7-foundation-deployer-vault-oidc-login.md`
before pickup (`.loop/config.json` sets `require_eval: true`, so the loop
refuses pickup until the marker exists). Co-author it with the
`create-eval` skill.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: BROKEN. Gate verdict: `fail`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/F7-foundation-deployer-vault-oidc-login.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: The `deployer` policy forbids the `sys/*` and `auth/*` writes that `terraform apply` of its own Terraform root performs. Eval row 3 asserts that denial as proof of correctness, so the guardrail certifies the broken result green.

This ticket is **`blocked`** (`unresolved-design-fork`). A1 applied no
structural fix here: the required fixes reverse design decisions or need an
operator call. **Do not implement from this plan as written.** Work the
verdict's required-fix list, then re-dispatch `loop-plan-reviewer` before
unblocking.

## Measured evidence, 2026-07-31

Measured against the live cluster after F2 was applied. Vault is **2.0.3** on
Consul storage. This section adds evidence; it does not resolve the fork or
unblock the ticket. Work the verdict's required-fix list and re-dispatch
`loop-plan-reviewer` as that section says.

### How it was measured

A throwaway policy `probe-nosudo` granting the deployer's paths with **no
`sudo` capability anywhere**, a 10-minute token against it, then each
operation attempted for real. The policy, the token and a scratch mount were
deleted afterwards; `vault secrets list`, `vault auth list` and `vault policy
list` were re-read to confirm the cluster came back to 8 mounts, 3 auth
methods and 5 policies.

The point of withholding `sudo` is that it is the only way to tell a
root-protected endpoint from a merely privileged one. Granting a broad policy
and watching it succeed cannot distinguish them.

### Result

| Operation | Terraform resource | Non-sudo token |
| --- | --- | --- |
| read/list `sys/mounts` | refresh of `vault_mount.kvv2` | OK |
| read/list `sys/auth` | refresh of `vault_auth_backend.userpass` | OK |
| create/read/update/delete `secret/*` | every `vault_kv_secret_v2` | OK |
| read `nomad/creds/deploy` | brokered Nomad token | OK |
| read `consul/creds/deploy` | brokered Consul token | OK |
| **enable a secrets mount** (`sys/mounts/*`) | `vault_mount.kvv2` create | **OK — no `sudo` required** |
| **enable an auth method** (`sys/auth/*`) | `vault_auth_backend.userpass` create | **DENIED without `sudo`** |

### What this changes

**The headline defect is narrower than recorded.** The verdict says the
policy "forbids the `sys/*` and `auth/*` writes that `terraform apply`
performs", and its table at `:45` lists `sys/mounts/<secret_mount>` among the
forbidden writes. On Vault 2.0.3 `sys/mounts/*` needs **no `sudo`**: an
ordinary `create`/`update` grant is enough. So of everything this Terraform
root writes, exactly **one** path is root-protected:

```
path "sys/auth/*" { capabilities = ["create","read","update","delete","sudo"] }
```

That one line is the whole distance between "the deployer runs unprivileged"
and where the repo is today. The rest of the fix is scoping breadth, not
privilege: `sys/policies/acl/*` for the policies the deployer owns,
`sys/mounts/*`, and now `identity/*`.

**`sys/auth/*` is a NEW requirement the verdict could not have seen.** The
verdict was written 2026-07-30, when the only auth backend was `jwt-nomad/`,
created by Ansible and outside Terraform. F2 applied on 2026-07-31 and added
`vault_auth_backend.userpass` to this Terraform root, so `sys/auth/userpass`
became a path the deployer writes. Anyone working the required-fix list from
the verdict alone will scope the policy against a resource set that is one
short.

**F2 widened the deployer's surface in three other ways**, all also
post-dating the verdict and all needing to appear in the policy: nine
`identity/*` objects (entity, alias, group, and the six `identity/oidc/*`
resources), a `vault_generic_endpoint` writing
`auth/userpass/users/operator`, and two more KV2 paths under
`secret/data/default/vault/`.

**Mitigating detail on `sys/auth/*`:** `vault_auth_backend.userpass` is
create-once and already exists, so a steady-state `apply` only reads the auth
table, which needs no `sudo`. A deployer without `sudo` therefore works
day-to-day and fails on a fresh bootstrap or any change to that resource —
the worst failure shape, since it passes every test until the day it matters.
Grant the `sudo` or move `vault_auth_backend` to Ansible, which already owns
the other auth backend. Do not leave it to be discovered.

### Brokering is proven end to end

F5 and F6 are `done` and the brokered path works against the live cluster, not
just in Vault:

- `vault read nomad/creds/deploy` mints a client token, 30-minute renewable
  lease. `nomad acl token self` reports `Type = client`, `Policies =
  [deploy]`. `nomad job status` and `nomad node status` both return **403**,
  which is `nomad_deploy_role.tf` working as designed. It grants
  `submit-job`/`read-job` and deliberately withholds `list-jobs`, node and
  agent access.
- `vault read consul/creds/deploy` mints a Consul token, 30-minute renewable
  lease. It reads the catalog and the `terraform/` KV prefix holding both
  Terraform states, and is refused `acl:read`.

So the deployer half of "one human login, brokered service tokens" needs no
new mechanism. What is missing is only the Vault policy that lets a human read
those two paths.

**Note for whoever scopes that policy:** the Consul `deploy` token can read
`terraform/applications` and `terraform/infrastructure`. It must, since that
is the state backend. Terraform state holds secrets in plaintext, so anyone
who can deploy can read every secret in state. This is not a regression, since
the static Consul token it replaces can do the same, but the brokered token is
not a containment boundary and should not be described as one.

### Do NOT set `token_ttl` on the operator login

D2's Q6 previously handed F7 a task: set `token_ttl`/`token_max_ttl` on the
operator `userpass` user so the 32-day session expires on its own. **The
operator reversed that on 2026-07-31. Do not do it.**

The reasoning is that the two credentials play different roles. The Vault
token is the long-lived credential a human holds and re-obtains by logging in,
roughly monthly. The brokered Nomad and Consul creds are the short-lived ones,
30 minutes, refreshed automatically by the CLI. Shortening the Vault token
would force a daily login without shortening anything that actually reaches
Nomad or Consul.

D2 §12 carries the full model. F7 should leave `auth_userpass.tf` alone on
this point and scope its work to the policy.

### F7 also owns the human read roles (added 2026-07-31)

`D4-cli-cluster-tui` Q2 asked which ticket should create a read-capable Nomad
role, since the `deploy` role withholds `list-jobs` and node access and a
monitoring panel built on it shows "denied" in both headline widgets. The
answer is **this ticket**, and the replan should absorb it.

The reasoning is about where the decision belongs, not convenience. `D2`
carries a guardrail forbidding it from authoring Terraform. `D3` needs the
same token for `status` and `service`, so building it in `D4` puts it in the
ticket that needs it second. Keeping every Vault and Nomad policy decision in
one ticket is also where the review attention already is.

What to add:

- A Nomad ACL policy granting `list-jobs`, `read-job` and node read on the
  `default` namespace, and nothing else. No `read-logs`, no `submit-job`, no
  `alloc-exec`.
- A `vault_nomad_secret_role` brokering it, so `D2` can read
  `nomad/creds/<name>` the way it reads `nomad/creds/deploy`.
- The matching grant in the operator policy.

**Do not reuse the existing `developer` Nomad policy for this.** It grants
`alloc-exec` and `alloc-node-exec`, which is shell access inside allocations
and on the node. A read-only panel must not hold it.
`G2-nomad-ui-oidc-login` Q1 owns bringing `developer` under management; that
is a separate concern from creating a narrow read role here.
