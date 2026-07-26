---
epic = "foundation"
depends_on = []
priority = 40
summary = "Make Nomad Workload Identity the cluster's machine-identity root: document the existing Nomad-to-Vault JWT trust chain, settle the identity-stanza audience convention for future non-Vault consumers, and prove keyless Vault reads with a scoped test job."
tags = ["nomad", "vault", "jwt", "docs"]
---

# F1: Establish Nomad Workload Identity as a trusted JWT issuer (foundation)

## Title

Make Nomad Workload Identity (WI) the cluster's single machine-identity
root: document the existing Nomad->Vault JWT trust chain, define the
`identity`-stanza audience convention for future non-Vault consumers
(MinIO STS in M1, service bearer auth), and prove keyless Vault secret
reads with a dedicated test job. Foundation for M1/S2/R3.

## Size / Effort

**Medium.** The Nomad->Vault trust chain already exists and works (built
in Ansible during bootstrap). The effort is not net-new plumbing; it is
(a) deciding where the trust config should live long-term (Ansible vs
Terraform, a real fork — see Open Questions), (b) writing the
convention doc that M1 will point MinIO at, (c) adding a scoped test job
plus a repeatable operator verification, and (d) reconciling the
audience-naming mismatch between the existing config (`vault.io`) and
the epic's examples (`vault`, `minio`). Effort is driven by the
Ansible/Terraform ownership decision, not by code volume.

## Triggered by

The localstack auth epic. Vault is confirmed as the human OIDC provider
(Zitadel dropped); Nomad WI JWTs are the machine identity. Every
downstream keyless path (M1 MinIO STS, S2/R3 Vault dynamic creds,
service bearer auth) must sit on one proven issuer. F1 is the bedrock
ticket with no upstream dependencies.

## Context (today's state)

The Nomad->Vault WI JWT trust chain is **already established**, but
entirely inside the Ansible bootstrap role, undocumented, and using a
single audience. Concretely:

- Nomad server issues a default WI JWT for Vault to every workload:
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:37-46` sets
  `vault { enabled = true ... default_identity { aud = ["vault.io"]
  ttl = "1h" } }`. Nomad ACLs are on
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:16-18`).
- Nomad exposes the OIDC/JWKS discovery endpoint on port 4646. This is
  proven by Vault being configured to pull keys from it:
  `bootstrap/roles/nomad_server/tasks/main.yml:216-226` writes
  `auth/jwt-nomad/config` with
  `jwks_url="http://127.0.0.1:4646/.well-known/jwks.json"` and
  `jwt_supported_algs="RS256,EdDSA"`. The Nomad API address in this
  cluster is `192.168.2.30:4646` (`docs/haproxy_reverse_proxy.md:12`,
  `docs/monitoring.md:17`). This is the same JWKS endpoint memex's
  application-level WI-JWT verification relies on; that reliance is what
  partly proves the issuance chain.
- Vault trusts Nomad as a JWT issuer via a dedicated auth backend:
  `bootstrap/roles/nomad_server/tasks/main.yml:207-214` runs
  `vault auth enable -path=jwt-nomad jwt`, configured at
  `tasks/main.yml:216-226` with `default_role="nomad-workloads"`.
- The role mapping WI claims to a policy:
  `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`
  sets `bound_audiences: ["vault.io"]` (line 3),
  `user_claim: "/nomad_job_id"` (line 4), and
  `claim_mappings` for exactly `nomad_namespace`, `nomad_job_id`,
  `nomad_task` (lines 6-10), with `token_policies: ["nomad-workloads"]`.
- The policy keyed on those claims:
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-24`
  (the WHOLE file — 24 lines, not the 11 an earlier draft of this plan
  cited). It grants:
  - `read` on `secret/data/{{nomad_namespace}}/{{nomad_job_id}}/*` and the
    bare path (`:1-7`), matching the
    `secret/data/<namespace>/<job_id>/<entry>` convention; **and**
  - `list` on `secret/metadata/{{nomad_namespace}}/*` and on
    `secret/metadata/*` (`:9-15`); **and**
  - **`read`, `create`, and `update` on `bootstrap/data/*`** (`:17-20`) plus
    `list` on `bootstrap/metadata/*` (`:22-24`).
- **THE POLICY IS NOT JOB-SCOPED, and the doc must say so.** Verified live
  2026-07-25 (`vault policy read nomad-workloads`, `vault list
  bootstrap/metadata`): the `bootstrap` mount holds `github` and `tailscale`
  — the GitHub PAT and the Tailscale auth key
  (`docs/credential-rotation.md:20,29`). Every workload on the cluster
  (minio, memex, hermes, grafana, postgres, and any probe job this ticket
  adds) can read AND overwrite both, and can enumerate every secret path in
  every namespace. Describing this policy as per-job scoped would ship a
  false claim about the cluster's blast radius in the one document
  downstream tickets are meant to trust. Narrowing it is NOT this ticket's
  job (see Non-goals); documenting it accurately is.
- Jobs consume it keylessly today with a bare `vault {}` block plus a
  `template { ... env = true }` using `{{ with secret "<path>" }}`:
  see `deployments/infrastructure/services/minio.hcl:30-40` and
  `deployments/applications/services/memex.hcl:44,46-60,114-141`. No job
  in the repo declares an explicit `identity` stanza; they all ride the
  implicit `default_identity` (aud `vault.io`).
- **A SECOND JWT role now exists, created in Terraform, and it changes the
  ownership story this ticket was written to settle.** F3 shipped after this
  plan was drafted. `vault list auth/jwt-nomad/role` returns `acme` and
  `nomad-workloads` once T3 is applied; before that apply it also returns the
  `haproxy` role, which T3 destroys. `deployments/infrastructure/acme.tf:41-90`
  declares `vault_policy.acme_tls_write` and
  `vault_jwt_auth_backend_role.acme` on the Ansible-created `jwt-nomad`
  mount, and `services/acme.hcl:73-75` selects it with
  `vault { role = "${vault_role}" }`. (F3 shipped the first instance of this
  pattern in `pki.tf`; T3 deleted that file, and the acme job is now the live
  example.) The real model is therefore a SPLIT:
  bootstrap-time root of trust (mount, config, default role, shared policy)
  in Ansible; per-job roles and policies in Terraform, alongside the engine
  they grant access to.
- **One task holds exactly one Vault token.** A task has a single `vault`
  block and performs a single JWT login, so naming a dedicated role
  REPLACES `nomad-workloads` rather than adding to it. That is exactly why
  `acme.tf:87` sets `token_policies` to BOTH `nomad-workloads` and the
  dedicated policy: the acme job needs a scoped grant AND ordinary KV reads,
  so its own role has to carry both. This is the single most useful sentence this document can
  contain, and every consumer (M1, S2/R3, F5/F6) will need it.
- **Nomad's OIDC discovery endpoint is DISABLED.**
  `curl http://192.168.2.30:4646/.well-known/openid-configuration` returns
  `OIDC Discovery endpoint disabled`; `/v1/agent/self` shows
  `oidc_issuer: ""`, and `grep -rn oidc_issuer bootstrap/ deployments/`
  finds nothing. `/.well-known/jwks.json` works (6 keys). This matters
  because MinIO's `identity_openid` consumes a discovery document, not a
  bare JWKS — see requirement 1 and Q6.
- The secret-path convention is already live and consistent: secrets
  are written at `default/<job>/<entry>` in
  `deployments/infrastructure/secrets.tf:16,38,53,74` and read back at
  the matching path, e.g. hermes reads
  `${var.secret_mount}/data/default/hermes/memex_auth`
  (`deployments/applications/services.tf:120`).

**What is wrong / missing:**

1. The trust chain is invisible. Nothing under `docs/` explains it, so
   M1 cannot "point MinIO's `identity_openid` at Nomad's JWKS" without
   reverse-engineering the Ansible role.
2. There is exactly one audience (`vault.io`) and no explicit
   `identity`-stanza convention. Non-Vault consumers (MinIO STS,
   service bearer auth) need distinct audiences and explicit `identity`
   stanzas with a defined token-delivery mode (file vs env). None
   exists.
3. The epic brief names audiences `vault` and `minio`; the running
   config uses `vault.io`. The mismatch is unreconciled and will break
   consumers if picked wrong.
4. There is no test artifact proving a job can authenticate to Vault
   via the jwt backend and read a scoped secret. The chain is asserted,
   not demonstrated.

## Non-goals / out of scope

- **Do not** implement MinIO STS / `identity_openid` (that is M1). F1
  only documents the JWKS endpoint and audience so M1 can consume them.
- **Do not** implement Vault dynamic database/PKI credential backends
  (S2/R3). F1 proves KV read via the jwt backend only.
- **Do not** touch the human OIDC (Vault-as-OIDC-provider) path.
- **Do not** re-key or rename the existing `vault.io` audience unless
  Open Question Q2 is resolved to do so; a silent rename breaks memex,
  minio, hermes, grafana, and every current workload at once.
- **Do not** add custom JWT claims. Nomad 1.11.3 rejects `extra_claims` in a
  task `identity` block (verified via `/v1/jobs/parse`: *"An argument named
  extra_claims is not expected here"*), so per-job custom claims are
  unavailable and scoping must key on `nomad_job_id` / `nomad_namespace`.
  Note the earlier draft justified this via `claim_mappings`, which is a
  Vault-side selector and cannot constrain what Nomad puts in the JWT — the
  conclusion holds, the reasoning did not.
- **Do not** widen the `nomad-workloads` Vault policy
  (`vault_nomad_workloads.hcl.j2`) beyond what the test job needs.
- **Do not narrow it either.** The `bootstrap/data/*` write grant documented
  in Context is a real over-grant, but fixing it is its own ticket with its
  own blast radius (every workload's token changes). F1 documents it and
  stops.

## Requirements & restrictions

**Must achieve:**

1. A single authoritative doc (suggest `docs/workload-identity.md`)
   describing: the JWKS endpoint and its cluster-internal URL, the
   `jwt-nomad` Vault backend, the `nomad-workloads` role and policy **as it
   actually is** (including the `bootstrap/data/*` write grant and the
   cluster-wide `secret/metadata/*` list — see Context), the fixed-claims
   constraint, the `secret/data/<namespace>/<job_id>/<entry>` convention,
   and the `identity`-stanza / audience convention for future consumers.
   The doc carries a threat-model section stating the real blast radius,
   not the intended one.
2. **The doc must document the Ansible/Terraform split and the one-token
   rule.** Specifically: per-job roles and policies go in Terraform beside
   the engine they grant (pattern `acme.tf:41-90`), are selected with
   `vault { role = "<name>" }`, and REPLACE `nomad-workloads` rather than
   adding to it — so a job needing both a scoped grant and KV reads must
   list both policies on its own role. Lead the convention section with the
   `name` field of the `identity` block; it is the load-bearing one.
3. A documented `identity`-stanza convention: one audience per **verifying
   service** (never per job — per-job distinction comes from
   `nomad_job_id`), and the file-vs-env token-delivery choice per consumer
   class, with a rule for when a job needs an explicit `identity` stanza
   versus riding the implicit Vault `default_identity`.
4. A test Nomad job that authenticates to Vault through `jwt-nomad` and
   reads a scoped KV secret, plus a written, repeatable operator
   verification proving it succeeds live. **The stanza must be
   `identity { name = "vault_default" ... }`** — see the Q5 resolution;
   a bare `identity {}` configures the task's default Nomad-API identity,
   not the Vault one, and proves nothing.
5. **State plainly what F1 does and does not deliver for M1.** It delivers
   the JWKS URL. It does NOT deliver an OIDC discovery document, because
   that endpoint is disabled (Context). Either resolve Q6 to enable it here
   or record in the doc and in M1's dependency that M1 owns enabling it.

**Fixed-claims constraint (call out prominently in the doc):** Nomad WI
JWTs carry three usable claims — `nomad_namespace`, `nomad_job_id`,
`nomad_task` — mapped into Vault alias metadata by the `claim_mappings` in
`bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json:6-10`.
Nomad 1.11.3 rejects `extra_claims` in a task `identity` block, so per-job
custom claims are unavailable (see Non-goals for the verification). All
Vault role/policy scoping must therefore key on `nomad_job_id` and
`nomad_namespace`; this is why the existing policy templates the secret path
from those two claims (`vault_nomad_workloads.hcl.j2:1-7`) and why the
secret convention is `secret/data/<namespace>/<job_id>/<entry>`.

**Repo principles to respect (cited):**

- Secrets live only in Vault KV2; never hardcode credentials
  (`CLAUDE.md`, "Secrets" convention; enforced by
  `detect-private-key` in `.pre-commit-config.yaml:12`).
- Surgical changes; match existing style; do not refactor working code
  (`CLAUDE.md` sections 2-3). The existing `vault.io` trust works —
  extend, do not rewrite it, absent a resolved fork.
- Simplicity first: no speculative audiences or roles beyond what F1's
  test and M1's documented need require (`CLAUDE.md` section 2).
- Every change ships with a test / verification; a bug or feature is not
  done until exercised (`.claude/rules/python-testing.md`
  `all-code-needs-tests`). This repo is IaC with no Python suite, so the
  "test" is the Nomad test job plus the written operator verification
  (see Tests & validation gates).
- Task runner is `just`; HCL is formatted with `nomad fmt`
  (`CLAUDE.md` "Key Conventions"; `justfile:9-10`).
- Docs must pass the slop scan before merge
  (`.claude/rules/slop-scan-for-docs.md`): no hallucinated paths/URLs,
  thesis-first, American spelling, minimal em-dashes.
- Adversarial review before declaring done
  (`.claude/rules/adversarial-reviews.md`).

## Code surface (exact anchors)

- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:37-46` — Nomad's
  `vault {}` + `default_identity { aud = ["vault.io"] }`. Read-only
  reference unless Q2/Q1 resolve to change the audience here.
- `bootstrap/roles/nomad_server/tasks/main.yml:198-271` — the imperative
  trust setup: enable `jwt-nomad` (207-214), configure JWKS
  (216-226), create role (236-242), create policy (257-271). This is
  the block a Terraform migration (Q1) would replace or import.
- `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json` —
  role: `bound_audiences` (3), `user_claim` (4), fixed `claim_mappings`
  (6-10), `token_policies` (12). Edit only if Q1/Q2 resolve to.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-24`
  — the shared policy IN FULL: the job-scoped read (`:1-7`), the
  cluster-wide metadata list (`:9-15`), and the `bootstrap/data/*`
  read/create/update (`:17-24`). Read-only reference; the doc describes all
  three. The test job's secret path must fall under
  `secret/data/<namespace>/<job_id>/*` for the first grant to cover it.
- `deployments/infrastructure/acme.tf:41-90` — **the live example of the
  Terraform half of the split**: `vault_policy.acme_tls_write` plus
  `vault_jwt_auth_backend_role.acme` on the Ansible-created `jwt-nomad`
  mount, with `claim_mappings` replicated. Note `token_policies`
  (`acme.tf:87`) lists BOTH `nomad-workloads` and the dedicated policy,
  because naming a role replaces the default rather than adding to it, so a
  job needing both grants must name both. Read-only reference; this is what
  the doc's convention section describes. (An earlier draft pointed at
  `providers.tf:7-10,28` as where such resources "would" land — they
  already landed, here.)
- `deployments/infrastructure/services/acme.hcl:73-75` — the consuming
  side: `vault { role = "${vault_role}" }`. Read-only reference.
- `deployments/infrastructure/secrets.tf:1-29` — KV2 mount and the
  `default/<job>/<entry>` secret pattern; the test job's scoped secret
  should be added here (or a sibling file) following this shape.
- `deployments/infrastructure/services.tf:293-306` — the
  `nomad_job` + `templatefile` deployment pattern; a Terraform-managed
  test job would follow it. Alternatively the test job is a standalone
  `*.hcl` run manually (Q4).
- `deployments/infrastructure/services/minio.hcl:30-40` and
  `deployments/applications/services/memex.hcl:44,46-60` — the current
  bare-`vault {}` + `template env=true` consumption pattern the doc must
  contrast against the explicit `identity`-stanza pattern.
- `docs/` (no existing auth/WI doc; `docs/architecture/` holds only PNGs)
  — new `docs/workload-identity.md` lands here.

## Tests & validation gates

**Prerequisite in a worktree:** run `just worktree_setup <path>`
(`justfile:30-32`, added in `3c12c7a`) BEFORE the first gate. The
`terraform-validate` hook has `pass_filenames: false`, so it runs on every
gate invocation regardless of what F1 touched, and it evaluates
`file("${path.root}/../../.ssh/id_rsa")` (`services.tf:287`), which is
gitignored and absent from a fresh worktree. Skip this and the gate red-fails
for a reason unrelated to the ticket.

**Repo gate:** `just pre_commit`, which runs `pre-commit run --all-files`
(`justfile:18-19`). Hooks (`.pre-commit-config.yaml`): `check-json`,
`check-ast`, `check-merge-conflict`, `check-yaml --unsafe`,
`debug-statements`, `detect-private-key`, `end-of-file-fixer`, local
`nomad-fmt` (`nomad fmt -recursive`) on `*.hcl` (lines 16-21), and local
`terraform-fmt` (`terraform fmt -check -recursive`, lines 22-27) plus
`terraform-validate` (`scripts/tf_validate.sh`, lines 28-33) on `*.tf`.
The gate is terraform-aware: `terraform-validate` runs `terraform
validate` against each root (`deployments/infrastructure`,
`deployments/applications`, `deployments/applications/modules/bucket`)
offline, so any `.tf` this ticket adds is caught for both fmt and
schema. `.loop/` and `.claude/` are excluded
(`.pre-commit-config.yaml:1`), so this ticket file is not linted; the
new `*.hcl`, `*.tf`, and `docs/*.md` files are. This gate proves
formatting, HCL/Terraform syntax, and schema; it does not exercise the
live JWT trust chain. The evals below do.

**Evals (live cluster).** The cluster is reachable through the
environment: `VAULT_ADDR` + `VAULT_TOKEN`, `NOMAD_ADDR` + `NOMAD_TOKEN`,
and `CONSUL_HTTP_ADDR`. F1's acceptance is runnable, not a manual
walkthrough. Each eval is a command plus its expected result. Run the
**pre-apply** evals before adding the test job (they confirm the trust
chain the ticket documents already exists); run the **at-close** evals
after the scratch job is deployed (they prove keyless secret reads end
to end).

Pre-apply (trust chain exists before F1 touches anything):

1. **Nomad JWKS reachable.**
   `curl -s "$NOMAD_ADDR/.well-known/jwks.json" | jq '.keys | length'`
   -> prints a number >= 1 (at least one signing key). This is the URL
   M1 will point MinIO's `identity_openid` at; the doc must cite it.
2. **`jwt-nomad` auth method exists.**
   `vault auth list -format=json | jq -e '."jwt-nomad/"'`
   -> exit 0 and a JSON object with `"type": "jwt"`. Confirms the
   backend at `bootstrap/roles/nomad_server/tasks/main.yml:207-226`.
3. **`nomad-workloads` role exists and binds the expected audience.**
   `vault read -format=json auth/jwt-nomad/role/nomad-workloads`
   -> exit 0; `.data.bound_audiences` contains `vault.io` and
   `.data.token_policies` contains `nomad-workloads`. Matches
   `vault_role_nomad_workloads.json:3,12`.
4. **Fixed-claims constraint holds.** From the same read,
   `.data.claim_mappings` maps exactly `nomad_namespace`,
   `nomad_job_id`, and `nomad_task` (no others), confirming custom
   claims are impossible (`vault_role_nomad_workloads.json:6-10`).

At-close (after the scratch test job is deployed):

5. **Operator precondition, NOT a WI proof.** Write the probe secret by
   hand (`vault kv put`, per Q4 — no Terraform state), then read it back:
   `vault kv get -mount=secret default/wi-test/probe`
   -> exit 0, non-empty value. This runs under the OPERATOR's token, so it
   proves only that the secret exists; it says nothing about the keyless
   path. Per Q3 the job id `wi-test` yields `secret/data/default/wi-test/*`,
   already covered by `vault_nomad_workloads.hcl.j2:1-7`, so no policy
   widening. Purge it at teardown.
6. **Scratch job runs.** `nomad job run tests/wi-vault-probe.nomad.hcl`,
   then `nomad job status -short wi-test`
   -> status `running` (service) or `complete` (batch); the alloc does
   not fail on template rendering.
7. **WI token authenticates to Vault and reads the scoped secret.** The
   task's `template { ... }` block renders the probe secret via
   `{{ with secret "secret/data/default/wi-test/probe" }}`; confirm the
   rendered file/env is non-empty in the alloc (`nomad alloc logs
   <alloc-id>` or `nomad alloc fs <alloc-id> <path>`).
   To prove the login leg directly, read the JWT the job renders at
   `secrets/nomad_vault_default.jwt` — which requires
   `identity { name = "vault_default" ... file = true }` on the task (Q5).
   The server-side `default_identity` has `File: null` and `Env: null`
   (`/v1/agent/self`), so with a bare `vault {}` there is NO JWT on disk to
   capture and this leg is unexecutable.
   Then `vault write -format=json auth/jwt-nomad/login role=nomad-workloads jwt=<wi-jwt>`
   -> exit 0, returning a client token whose `token_policies` include
   `nomad-workloads`.
8. **Negative case: another job's path is denied.** Using the token from
   eval 7, `vault kv get -mount=secret default/other-job/probe`
   -> HTTP 403 / permission denied.
   **Assert only what this proves:** reads under a DIFFERENT job's
   `secret/data/` prefix are denied. It does NOT prove the token is
   job-scoped generally — it is not (Context). Pair it with the companion
   below so the doc records reality.
9. **Companion: the over-grant is real.** Using the same token,
   `vault kv get -mount=bootstrap github`
   -> **succeeds**, demonstrating that every workload can read (and per the
   policy, overwrite) the bootstrap credentials. Record this in the doc's
   threat-model section. A green eval 8 without this one licenses a false
   conclusion.

Record the eval commands and their observed results in
`docs/workload-identity.md` so the acceptance stays repeatable. Then
stop the scratch job (`nomad job stop -purge wi-test`) per Q4 so no
standing test job is left behind.

**Required artifacts:** the scratch job spec
`tests/wi-vault-probe.nomad.hcl` (formatted by `nomad fmt`), carrying

```
identity {
  name        = "vault_default"
  aud         = ["vault.io"]
  file        = true
  change_mode = "restart"
}
```

per the corrected Q5 — the `name` is load-bearing, see that resolution. Plus
the hand-written probe secret, the eval transcript in the doc, and a green
`just pre_commit` on every added/changed file.

**Eval marker (Definition of Done, five-column scenarios):**
`.loop/evals/F1-foundation-nomad-wi-jwt-trust.md`.

## Risk assessment

- **Blast radius (high if the existing trust is touched).** The
  `vault.io` audience, the `jwt-nomad` backend, the `nomad-workloads`
  role, and its policy are load-bearing for every running workload
  (minio, memex, hermes, grafana, postgres, etc.). Renaming the
  audience or re-pointing the backend breaks all of them at once. F1's
  safe path is additive: document + add a scoped test + (optionally) a
  new audience for future consumers, leaving `vault.io` intact.
- **Reversibility.** Doc and test job are trivially reversible. A
  Terraform migration of the jwt backend (Q1) is the least reversible
  step: it risks Terraform and Ansible fighting over the same Vault
  objects (drift, or a destroy on the next `terraform apply`). Requires
  `terraform import` and removal from the Ansible role in the same
  change, or explicit dual-ownership avoidance.
- **Likeliest failure modes.** (a) Audience mismatch: test job requests
  an audience the role does not bind, so Vault rejects with 403. (b)
  Secret path outside the policy's job-id template, so read is denied
  despite valid auth. (c) Silent rename of `vault.io` cascading an
  outage. (d) Migrating trust into Terraform without importing the
  Ansible-created backend, causing duplicate-mount errors or a
  destroy/recreate.

## Subtickets (ordered, dependency-aware)

1. **Reconcile audience naming (blocks all else).** Resolve Q2. Decide
   whether the machine-identity audiences are `vault.io` (keep) plus new
   distinct ones for new consumers, or a rename. Record the decision in
   the doc. No code change if "keep + add".
2. **Decide trust-config ownership.** Resolve Q1 (Ansible stays
   authoritative vs migrate to Terraform). Record it. If "migrate",
   scope the `import` + Ansible-removal as its own step.
3. **Author `docs/workload-identity.md`.** The JWKS endpoint URL, the
   backend/role/policy, the fixed-claims constraint, the secret-path
   convention, the `identity`-stanza + audience + file-vs-env
   convention, and the explicit "M1 points MinIO `identity_openid` at
   `<JWKS URL>`" line. Passes the slop scan.
4. **Add the probe secret + test job.** Per Q4 the secret is written by
   hand with `vault kv put` and purged at teardown — NOT added to
   `secrets.tf`. Terraform-managing a throwaway probe would leave permanent
   state and require an apply against `deployments/infrastructure`, which
   would also re-evaluate F3's PKI and haproxy resources. The job is the
   standalone `tests/wi-vault-probe.nomad.hcl` with the named identity
   stanza from Q5.
5. **Write and run the operator verification.** Execute on the live
   cluster, capture the positive and negative results in the doc.
6. **Run `just pre_commit` and the adversarial review.**

## Open questions (forks the operator must settle)

- **Q1 — Where does the Vault-side trust config live long-term?** The
  epic brief says "mostly Terraform (`vault_jwt_auth_backend` +
  `vault_jwt_auth_backend_role`)," but that config already exists and
  runs in Ansible (`bootstrap/roles/nomad_server/tasks/main.yml:198-271`).
  Options: (a) leave it in Ansible as the bootstrap-time root of trust
  and have F1 only document + test + add new audiences; (b) migrate the
  backend/role/policy into `deployments/infrastructure` Terraform,
  which requires `terraform import` of the live objects and removing
  them from the Ansible role in the same change to avoid dual-management
  drift. **Recommendation: (a) for F1.** The trust must exist before
  Terraform can even authenticate to Vault, so bootstrap is its natural
  home; migrating it is a separate, higher-risk refactor that should not
  block this foundation. Keep F1 additive.
- **Q2 — Audience naming.** Existing config uses `aud = ["vault.io"]`
  (`nomad.hcl.j2:43`, role `bound_audiences` line 3). The brief's
  examples use `vault` and `minio`. **Recommendation:** keep `vault.io`
  for the existing Vault path (renaming breaks every workload) and
  introduce new, distinct audiences (e.g. `minio`) only for new
  consumer classes as they arrive in M1. Document both.
- **Q3 — Does the test secret fit the existing policy, or add a policy
  path?** The `nomad-workloads` policy only grants
  `secret/data/<namespace>/<job_id>/*`
  (`vault_nomad_workloads.hcl.j2:1-11`). **Recommendation:** name the
  test job so its `nomad_job_id` yields a path already covered (e.g.
  job `wi-test` reading `secret/data/default/wi-test/probe`); no policy
  change needed, which keeps F1 minimal.
- **Q4 — Test job: Terraform-managed or standalone manual HCL?**
  A Terraform `nomad_job` (like `services.tf:293-306`) makes it part of
  the tracked infra but leaves a permanent test job running; a
  standalone `*.hcl` run by hand keeps infra clean but is less
  discoverable. **Recommendation:** a standalone
  `tests/wi-vault-probe.nomad.hcl` (mirroring the existing
  root-level `rescue-ssh.nomad.hcl` pattern) run via the operator
  verification, then stopped. It proves the chain without leaving a
  standing job or entangling Terraform state.
- **Q5 — Does the test job use an explicit `identity` stanza or the
  implicit Vault `default_identity`?** Vault access today works with a
  bare `vault {}` block and no explicit `identity` stanza. To also
  exercise the explicit-stanza convention F1 is defining, the test job
  could declare `identity { aud = ["vault.io"], ... }` explicitly.
  **Recommendation:** declare it explicitly so the test doubles as the
  worked example the doc references for M1's non-Vault consumers.
- **Q6 — File vs env token delivery in the documented convention.**
  Existing Vault consumption is env-based via `template env=true`.
  MinIO STS (M1) will likely need a token file. **Recommendation:**
  document env delivery as the default for Vault-templated secrets and
  file delivery for consumers that read a raw JWT (flag MinIO as
  file-based, to be confirmed by M1). Do not implement M1's choice here.

## Resolved forks (operator, 2026-07-23)

- **Q1 → Ansible keeps the ROOT of trust; Terraform owns per-job roles.**
  *(Amended 2026-07-25: the original resolution said "no Terraform
  migration" and was overtaken by F3 the same evening.)* The mount,
  `config`, the `nomad-workloads` default role, and the shared policy stay
  in Ansible — they must exist before Terraform can authenticate to Vault at
  all. But per-job `vault_jwt_auth_backend_role` + `vault_policy` resources
  now live in Terraform beside the engine they grant, as shipped in
  `acme.tf:41-90` and consumed via `vault { role = ... }`
  (`services/acme.hcl:73-75`). F1 documents this split; it migrates nothing.
- **Q2 → Keep `vault.io`; one audience per VERIFYING SERVICE.** Retain
  `vault.io` for the existing Vault path (renaming breaks every running
  workload). Add a distinct audience only per new consumer class that
  verifies tokens — `minio` for MinIO, and so on.
  *(Amended 2026-07-25: the original wording gave `memex` its own audience.
  That confuses the audience with the client. `minio` is a verifier; memex
  is a client job. Giving memex its own `aud` would force MinIO to run a
  second `identity_openid` provider with `client_id = memex`, contradicting
  M1's single-provider design. Per-job distinction comes from
  `nomad_job_id`, which is exactly what M1's R4 keys on — never from
  `aud`.)*
- **Q3 → Fit the existing policy path.** Name the test job so its
  `nomad_job_id` yields a path already covered by `nomad-workloads`
  (e.g. `secret/data/default/wi-test/probe`). No policy change.
- **Q4 → Standalone `tests/wi-vault-probe.nomad.hcl`.** Mirror the
  `rescue-ssh.nomad.hcl` pattern; run via operator verification, then
  stop it. No standing test job, no Terraform state entanglement.
- **Q5 → Explicit `identity` stanza, NAMED `vault_default`.**
  *(Corrected 2026-07-25.)* The original resolution said
  `identity { aud = ["vault.io"], ... }`. Verified against live Nomad
  1.11.3 via `/v1/jobs/parse`: an UNNAMED `identity` block configures the
  task's **default** workload identity — the one used against Nomad's own
  API — not the Vault identity, which is named `vault_<cluster>`.
  `/v1/agent/self` confirms the cluster is `default`, so the correct
  override is:

  ```
  identity {
    name        = "vault_default"
    aud         = ["vault.io"]
    file        = true
    change_mode = "restart"
  }
  ```

  The original form was wrong three ways: it is a no-op for Vault (the job
  would still log in via the server-side `default_identity`, proving nothing
  a bare `vault {}` does not); it silently retargets the task's Nomad-API
  identity audience, which is semantically wrong; and since the server
  default has `File: null`, no JWT is written to the alloc, making eval 7
  unexecutable. It would also have handed M1 a template that cannot work —
  M1's own R2/E2 depend on the named form
  (`identity { name = "minio" aud = ["minio"] file = true }`, confirmed to
  parse).
- **Q6 → Env default, file for raw-JWT consumers.** Document env
  delivery (`template env=true`) as the default; file delivery for
  consumers that read a raw JWT (flag MinIO as file-based, confirm in
  M1). Both carry ephemeral credentials — no static secret reintroduced.

## Open question added 2026-07-25 (operator must settle before pickup)

- **Q7 — Does F1 enable Nomad's OIDC discovery endpoint, or does M1?**
  F1's requirement 1 promises "the JWKS URL M1 will point MinIO at", and
  eval 1 checks `/.well-known/jwks.json`, which works. But MinIO's
  `identity_openid` consumes an OIDC **discovery document**
  (`MINIO_IDENTITY_OPENID_CONFIG_URL`), and
  `/.well-known/openid-configuration` returns `OIDC Discovery endpoint
  disabled` — `oidc_issuer` is unset cluster-wide. Enabling it means adding
  `server { oidc_issuer = ... }` to
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` and restarting the
  single Nomad server (`bootstrap_expect = 1`) — a file F1 currently marks
  read-only. As written, F1 closes green and M1 opens to discover its stated
  dependency was never delivered.
  *Recommendation:* add it as a subticket here, since F1 is the ticket that
  owns the trust chain and the restart is a one-time cost better paid before
  M1 depends on it. **Safety note, verified:** `auth/jwt-nomad/config` has
  `bound_issuer: ""`, so setting `oidc_issuer` — which changes the `iss`
  claim on newly minted WI JWTs — will NOT invalidate existing Vault logins.
  The risk is the server restart, not the claim change. If the operator
  prefers to defer, amend F1's non-goals and M1's dependency edge to say
  explicitly that F1 delivers JWKS only.
