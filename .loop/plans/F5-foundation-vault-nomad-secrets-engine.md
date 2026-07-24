---
epic = "foundation"
depends_on = []
priority = 60
---

# F5: Broker the Terraform deployer's Nomad token through Vault's Nomad secrets engine (foundation)

## Amendment (post-review, 2026-07-24)

The first implementation passed its Definition of Done but the adversarial
review proved a Major gap: the `deploy` policy as originally scoped
(`submit-job` + `read-job` only) cannot manage the 8
`nomad_dynamic_host_volume` resources co-located in the
`deployments/infrastructure` root — the minted token could not even read
them — so F8's cutover of that root would fail. The operator resolved the
fork: a single `deploy` policy, widened to also manage dynamic host
volumes, shared by both roots.

Mechanism note (discovered empirically on the live Nomad v2.0.3 cluster):
managing dynamic host volumes is governed by **namespace-level**
`host-volume-*` capabilities (`host-volume-create`, `-register`, `-read`,
`-write`, `-delete`), NOT by a `host_volume "*" { policy = "write" }`
block. That block's only valid capabilities are `mount-readonly` /
`mount-readwrite`, which govern a *job* mounting a volume — irrelevant to a
deployer that creates volumes but never mounts them. The `deploy` policy
therefore adds the five namespace `host-volume-*` capabilities and no
`host_volume` mount block.

Consequence for the "narrower than `developer`" framing: `developer`'s
namespace block uses the coarse `policy = "write"`
(`nomad_developer_policy.hcl:5`), which on Nomad v2.0.3 expands to include
the `host-volume-*` management capabilities — so `developer` itself *can*
manage dynamic host volumes (verified live: a `developer`-only token lists
all 8). `deploy` grants those five capabilities explicitly (rather than via
a coarse `policy` alias) and remains effectively a strict subset of
`developer`: strictly narrower on `alloc-exec` / `alloc-node-exec` /
`list-jobs` / `dispatch-job` / `read-logs` / `read-fs` / `node` / `agent` /
`operator` (all absent), and no broader on host-volume management. The
original `deploy` failed on host volumes not because `developer` lacked the
caps, but because that first `deploy` granted neither `policy = "write"`
nor the explicit `host-volume-*` caps. Requirement 3 and the eval marker
are amended accordingly below.

## Title

Make Vault mint the deployer's Nomad ACL token instead of a static
bootstrap/management token: enable Vault's Nomad secrets engine in Ansible
bootstrap (privileged one-time work), and add a Terraform-owned `deploy`
role plus a scoped `deploy` Nomad ACL policy so `vault read
nomad/creds/deploy` returns a short-lived, least-privilege token narrower
than the existing broad `developer` policy. Foundation for F8's provider
cutover; exact parallel of F6 (Consul).

## Size / Effort

**Medium.** No net-new trust plumbing is invented: the Nomad management
token that configures the engine already exists in Ansible
(`bootstrap/roles/nomad_server/tasks/main.yml:157-164`), and the Terraform
Vault provider (`~>5.3.0`) already ships the exact resources needed
(`vault_nomad_secret_backend`, `vault_nomad_secret_role` — both confirmed
present in the pinned provider binary). Effort is driven by (a) the
config split across two layers (Ansible enables + configures the engine;
Terraform owns the role + the scoped Nomad ACL policy), (b) authoring a
`deploy` Nomad ACL policy that is provably narrower than `developer`
while still able to `terraform apply` every existing `nomad_job`, and (c)
proving the negative capability (an out-of-scope action is denied by the
minted token) on the live cluster. Code volume is small; the care is in
the scope boundary and the two-layer ownership.

## Triggered by

The localstack auth epic. Vault is the confirmed identity root: F1
established the Nomad Workload-Identity JWT trust for in-cluster
workloads, F2 makes Vault the human OIDC provider. The 16 existing
tickets cover only two identity classes — humans (OIDC) and in-cluster
workloads (Nomad WI). This F5-F8 sub-feature covers the third class the
epic missed: the privileged Terraform deployer (this repo) that
provisions Vault/Nomad/Consul and today authenticates with god-mode
static bootstrap tokens read from the environment. F5 is the first step:
Vault becomes the broker for the deployer's Nomad token, exactly as the
MinIO and Postgres providers already pull their admin creds from Vault
today (`deployments/applications/providers.tf:40-53`).

## Context (today's state)

The deployer authenticates to Nomad with a long-lived static token, and
Vault has no Nomad secrets engine at all. Concretely:

- The deployer's Nomad provider is the bare `provider "nomad" {}` in both
  Terraform roots (`deployments/applications/providers.tf:30` and
  `deployments/infrastructure/providers.tf:26`), which reads `NOMAD_TOKEN`
  (and `NOMAD_ADDR`) from the environment.
- That `NOMAD_TOKEN` is sourced from `.devcontainer/.env` (template
  `.devcontainer/.env.example:2` `NOMAD_TOKEN=...`). The `applications`
  root loads it via `set dotenv-filename := "../../.devcontainer/.env"`
  (`deployments/applications/justfile:3`). The `infrastructure` root's
  justfile has **no** `set dotenv-filename` line
  (`deployments/infrastructure/justfile:1-6`); its `NOMAD_TOKEN` comes
  from the ambient devcontainer environment, not a justfile-loaded
  dotenv. Both ultimately read the same static token from the env.
- The static Nomad token originates from ACL bootstrap in Ansible:
  `bootstrap/roles/nomad_server/tasks/main.yml:141-164` runs `nomad acl
  bootstrap -json`, stores it at `/opt/nomad/init.json`, and lifts its
  `SecretID` into the `nomad_bootstrap_token` fact. This is the Nomad
  **management** token — full god-mode.
- The only Nomad ACL policy the repo defines today is the broad
  `developer` policy: `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl:1-33`,
  applied imperatively at `bootstrap/roles/nomad_server/tasks/main.yml:174-187`
  with the bootstrap token. It grants, on namespace `default`:
  `submit-job, read-job, list-jobs, dispatch-job, read-logs, read-fs,
  alloc-exec, alloc-lifecycle, alloc-node-exec` (lines 6-16), plus
  `host_volume "*" { policy = "write" }` (19-22) and `node`/`agent`/
  `operator` read (24-33). Far broader than a deployer needs.
- Vault's only mount today is the KV2 secret engine:
  `deployments/infrastructure/secrets.tf:2-7` (`vault_mount.kvv2`). There
  is **no** Nomad or Consul secrets engine anywhere — this is greenfield.
  All existing `vault_*` deployer-managed resources live in
  `deployments/infrastructure/secrets.tf` alongside `provider "vault" {}`
  (`deployments/infrastructure/providers.tf:7-10,28`).
- The Terraform Vault provider is `hashicorp/vault ~>5.3.0`
  (`deployments/infrastructure/providers.tf:7-10`). The pinned provider
  binary ships both `vault_nomad_secret_backend` and
  `vault_nomad_secret_role` (confirmed via
  `resource_nomad_secret_backend.go` / `resource_nomad_secret_role.go` in
  the provider), so the role side needs no new provider or version bump.

**What is wrong / missing:**

1. The deployer holds a static, long-lived Nomad **management** token
   with god-mode over the whole cluster. It never rotates and is only as
   safe as `.devcontainer/.env`.
2. Vault brokers KV, MinIO, and Postgres creds for the deployer, but not
   the deployer's own Nomad token — the one credential that grants the
   most. The broker pattern stops exactly where it matters most.
3. There is no least-privilege Nomad policy for "deploy this repo's
   jobs." The narrowest thing that exists is `developer`, which is a
   debugging policy (alloc-exec, host-volume write, operator read), not a
   deploy policy.

## Non-goals / out of scope

- **Not the Consul secrets engine.** The exact-parallel Consul version is
  F6 (`F6-foundation-vault-consul-secrets-engine`); F5 touches only Nomad.
- **Not the operator OIDC login** (F7) and **not the provider cutover**
  (F8). F5 must **not** change either `provider "nomad" {}` block, must
  **not** remove `NOMAD_TOKEN` from `.devcontainer/.env.example`, and must
  **not** wire the providers to consume `nomad/creds/deploy`. F8 depends on
  F5 and does that. F5 only makes `vault read nomad/creds/deploy` work.
- **Not CI / GitHub-Actions auth.** Deferred entirely for now (see
  `C1-cicd-tailscale-github-actions-deploy.md` for the CI track).
- **Do not retire the `developer` policy** in this ticket. It is still
  applied by Ansible and may be used by humans; note its future removal as
  downstream cleanup only.
- **Do not** widen the `deploy` role/policy beyond what a
  `terraform apply` of this repo's `nomad_job` **and**
  `nomad_dynamic_host_volume` resources actually needs (see Amendment).
  No speculative capabilities.

## Requirements & restrictions

**Must achieve:**

1. **Ansible (privileged one-time work):** enable and configure Vault's
   Nomad secrets engine during bootstrap. `vault secrets enable nomad`
   (idempotently, mirroring the existing "check then enable" pattern used
   for the jwt-nomad auth method at
   `bootstrap/roles/nomad_server/tasks/main.yml:198-214`), then configure
   the engine with the cluster's Nomad **management** token — the
   `nomad_bootstrap_token` fact already set at `tasks/main.yml:162-164`
   and the Nomad address. Vault uses that management token to mint scoped
   child tokens on demand. This is the privileged step that legitimately
   belongs in bootstrap because the bootstrap token already lives there.
2. **Terraform (deployer-owned):** in `deployments/infrastructure`, add
   the scoped `deploy` Nomad ACL policy and a `vault_nomad_secret_role`
   named `deploy` that references it, so `vault read nomad/creds/deploy`
   returns a token carrying only that policy. The role sets the short
   lease (see TTL below). This is the part the deployer legitimately owns,
   alongside the existing `vault_*` resources in `secrets.tf`.
3. **The `deploy` Nomad ACL policy must be purpose-scoped (see Amendment
   for the revised framing).** On namespace `default` it grants `submit-job`
   and `read-job` (enough to `terraform apply` this repo's `nomad_job`s),
   plus the five namespace `host-volume-*` capabilities
   (`host-volume-create`, `-register`, `-read`, `-write`, `-delete`)
   required to manage the 8 `nomad_dynamic_host_volume` resources in the
   `deployments/infrastructure` root. It must NOT grant: `alloc-exec` /
   `alloc-node-exec`, `list-jobs`, `dispatch-job`, `read-logs`, `read-fs`,
   or any `node` / `agent` / `operator` capability. Contrast this against
   every capability in `nomad_developer_policy.hcl:6-33` and confirm each
   excluded one is absent; `deploy` is strictly narrower than `developer`
   on all of those axes. On host-volume management `deploy` is no broader
   than `developer` — `developer`'s coarse `policy = "write"` already
   expands to the `host-volume-*` caps on Nomad v2.0.3, so `deploy`
   (granting them explicitly) is effectively a subset of `developer`.
4. **TTL:** a short lease (~30-60 min) that auto-renews during a run. Set
   `ttl` / `max_ttl` on the `vault_nomad_secret_role` accordingly; the
   auto-renew during a `terraform apply` run is Vault lease renewal
   behavior the deployer gets for free once F8 consumes the lease — F5
   only fixes the lease length so the credential is short-lived.
5. **Config-split boundary held:** Ansible does `secrets enable` +
   engine `config/access` (needs the management token). Terraform does the
   role + policy only. Terraform must NOT try to enable the mount or write
   the management token (it does not hold it and should not).

**Repo principles to respect (cited):**

- Secrets live only in Vault; never hardcode credentials (`CLAUDE.md`,
  "Secrets" / "Key Conventions"; enforced by `detect-private-key` in
  `.pre-commit-config.yaml:12`). The Nomad management token that
  configures the engine must stay the Ansible-held bootstrap token, never
  committed. A minted `deploy` token is short-lived by construction.
- Surgical changes; match existing style; do not refactor working code
  (`CLAUDE.md` sections 2-3). The `developer` policy and both
  `provider "nomad" {}` blocks are working — leave them intact. F5 is
  purely additive.
- Simplicity first: no capabilities, roles, or config beyond what
  `terraform apply` of this repo needs (`CLAUDE.md` section 2).
- Every change ships with a test / verification; a feature is not done
  until exercised (`.claude/rules/python-testing.md`
  `all-code-needs-tests`). This is IaC with no Python suite, so the
  "test" is the live-cluster evals below, including the negative-capability
  proof.
- Task runner is `just`; HCL is formatted with `nomad fmt` and Terraform
  with `terraform fmt` (`CLAUDE.md` "Key Conventions"; root `justfile:9-10`).
- Adversarial review before declaring done
  (`.claude/rules/adversarial-reviews.md`).
- Any docs added pass the slop scan (`.claude/rules/slop-scan-for-docs.md`):
  thesis-first, real paths/URLs, American spelling, minimal em-dashes.

## Code surface (exact anchors)

- `bootstrap/roles/nomad_server/tasks/main.yml:157-164` — where the
  `nomad_bootstrap_token` (Nomad management token) fact is set; the F5
  Ansible tasks reuse this fact to configure the engine, added after the
  existing developer-policy block (ends line 187) and near the existing
  Vault-side setup (starts line 189).
- `bootstrap/roles/nomad_server/tasks/main.yml:198-214` — the existing
  "check auth list, then enable" idempotency pattern for `jwt-nomad`; the
  new `vault secrets enable nomad` tasks mirror this shape (check
  `vault secrets list -format=json`, enable when absent, then write
  `nomad/config/access`). Uses `VAULT_TOKEN: "{{ vault_bootstrap_token }}"`
  and `VAULT_ADDR` exactly as lines 200-204 do.
- `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl:1-33` —
  the broad policy the new `deploy` policy must be provably narrower than.
  Read-only reference; do not edit or remove it.
- `deployments/infrastructure/providers.tf:7-10,28` — Vault provider
  `~>5.3.0` and `provider "vault" {}`; the home root for the new
  `vault_nomad_secret_role` (+ its Nomad ACL policy resource). No version
  bump needed.
- `deployments/infrastructure/secrets.tf:2-7` — the existing
  `vault_mount.kvv2` and the file where deployer-owned `vault_*` resources
  live; the new `vault_nomad_secret_role` "deploy" and the Nomad ACL
  policy land here or in a sibling `*.tf` in the same root following this
  file's resource style.
- `deployments/infrastructure/providers.tf:3-6` — the `hashicorp/nomad
  ~>2.5.0` provider already present in this root, which offers
  `nomad_acl_policy` for authoring the scoped `deploy` policy as Terraform
  (the role-side alternative to the `deploy` policy being managed
  imperatively in Ansible — see Open Question Q1).
- `deployments/applications/providers.tf:30` and
  `deployments/infrastructure/providers.tf:26` — the two `provider "nomad"
  {}` blocks. Read-only for F5; F8 rewires them. Cited so the implementer
  knows NOT to touch them.
- `deployments/applications/providers.tf:40-53` — the existing pattern of
  a provider consuming Vault-brokered creds (MinIO, Postgres via
  `ephemeral.vault_kv_secret_v2`). The reference shape F8 will follow for
  Nomad; cited here only as the target the F5 role enables.
- `deployments/infrastructure/justfile:1-6` and
  `deployments/applications/justfile:3` — how each root sources
  `NOMAD_TOKEN` today (ambient env vs `set dotenv-filename`). Read-only;
  F5 changes neither.
- `.devcontainer/.env.example:2` — `NOMAD_TOKEN=`; read-only, do NOT
  remove (that is F8).

## Tests & validation gates

**Repo gate:** `just pre_commit`, which runs `pre-commit run --all-files`
(root `justfile:16-18`). Hooks (`.pre-commit-config.yaml`): `check-json`,
`check-ast`, `check-merge-conflict`, `check-yaml --unsafe`,
`debug-statements`, `detect-private-key`, `end-of-file-fixer`, local
`nomad-fmt` (`nomad fmt -recursive`) on `*.hcl` (lines 16-21), local
`terraform-fmt` (`terraform fmt -check -recursive`, lines 22-27), and
`terraform-validate` (`scripts/tf_validate.sh`, lines 28-33) which runs
`terraform validate` offline against each root, including
`deployments/infrastructure`. Any `*.tf` or `*.hcl` this ticket adds is
caught for fmt and schema. `.loop/` and `.claude/` are excluded
(`.pre-commit-config.yaml:1`), so this ticket file is not linted; the new
`*.tf` (and any `*.hcl` policy file) are. This gate proves formatting,
HCL/Terraform syntax, and provider schema; it does not exercise the live
engine. The evals below do.

**Evals (live cluster).** The cluster is reachable through the
environment: `VAULT_ADDR` + `VAULT_TOKEN`, `NOMAD_ADDR` + `NOMAD_TOKEN`.
F5's acceptance is runnable. Run the setup evals after the Ansible engine
config and `terraform apply` of the role/policy.

1. **Nomad secrets engine is mounted.**
   `vault secrets list -format=json | jq -e '."nomad/"'`
   -> exit 0, a JSON object with `"type": "nomad"`. Confirms the Ansible
   `vault secrets enable nomad` step ran.
2. **Engine is configured with a management token.**
   `vault read -format=json nomad/config/access | jq -e '.data.address'`
   -> exit 0, prints the Nomad address. Confirms `nomad/config/access`
   was written by Ansible (the management token itself is not readable
   back, by design).
3. **The `deploy` role exists and carries only the `deploy` policy.**
   `vault read -format=json nomad/role/deploy`
   -> exit 0; `.data.policies` is exactly `["deploy"]` (no `management`
   type, no extra policies), and the role's `ttl` is <= ~3600s
   (short-lease requirement).
4. **`vault read nomad/creds/deploy` mints a short-lived token.**
   `vault read -format=json nomad/creds/deploy`
   -> exit 0, returns `.data.secret_id` and `.data.accessor_id`, with a
   `lease_duration` in the ~30-60 min band and `lease_id` set (so it can
   auto-renew during a run).
5. **Positive capability: the minted token can deploy.** Export the minted
   `secret_id` as `NOMAD_TOKEN` and run a read-only submit check against
   an existing job, e.g.
   `NOMAD_TOKEN=<minted> nomad job plan deployments/infrastructure/services/minio.hcl`
   (or `nomad job status -short <existing-job>` for `read-job`)
   -> exit 0 / plan renders. The token can submit and read jobs on
   `default`. (Use `nomad job plan` rather than a live `run` to avoid
   mutating the cluster during acceptance.)
6. **Negative capability (the core proof): out-of-scope actions are
   denied.** Using the same minted token, each of these must be refused:
   - `NOMAD_TOKEN=<minted> nomad alloc exec -task <t> <alloc-id> /bin/sh`
     -> permission denied (no `alloc-exec`).
   - `NOMAD_TOKEN=<minted> nomad node status`
     -> permission denied (no `node` read).
   - `NOMAD_TOKEN=<minted> nomad operator raft list-peers`
     -> permission denied (no `operator` capability).
   This proves the `deploy` policy is strictly narrower than `developer`
   (`nomad_developer_policy.hcl:6-33`), which would allow all three.
7. **`developer` policy untouched.**
   `NOMAD_TOKEN=$NOMAD_TOKEN nomad acl policy info developer`
   (using the ambient management token) -> still lists the original
   capabilities; F5 neither edited nor removed it.

**Required artifacts:** the Terraform `vault_nomad_secret_role` "deploy"
and the scoped Nomad ACL policy (Terraform `nomad_acl_policy` per Q1, or
an Ansible-applied `*.hcl` policy file per Q1's alternative), the Ansible
tasks enabling + configuring the engine (idempotent), the eval transcript
recorded so acceptance stays repeatable, and a green `just pre_commit` on
every added/changed file.

**Eval marker (Definition of Done, five-column scenarios):**
`.loop/evals/F5-foundation-vault-nomad-secrets-engine.md` (author with the
`create-eval` skill before implementation).

## Risk assessment

- **Blast radius (low-to-medium, and isolated).** F5 is additive: a new
  Vault mount and a new role/policy. It changes no existing
  provider block, no existing policy, and no running workload. The
  deployer keeps using its static token until F8, so a broken `deploy`
  role cannot lock the deployer out. The one shared object touched is the
  Nomad management token, and only as a **read** input to the engine
  config; it is not rotated or invalidated.
- **Reversibility.** Fully reversible: `vault secrets disable nomad`
  removes the engine and every token it minted; `terraform destroy` of the
  role/policy is clean. No state migration, no import.
- **Likeliest failure modes.** (a) The `deploy` policy is too narrow and
  `terraform apply` of a `nomad_job` fails on a missing capability — caught
  by eval 5 before F8 depends on it; widen only to the exact missing
  capability, never to `developer`. (b) The `deploy` policy is
  accidentally as broad as `developer` (copy-paste), defeating the point —
  caught by the eval 6 negative-capability proof. (c) Dual ownership if
  the `deploy` **policy** is authored in BOTH Ansible and Terraform
  (`nomad_acl_policy`), causing drift — Q1 must pick exactly one home. (d)
  Engine configured with a non-management Nomad token, so Vault cannot
  mint child tokens — caught by eval 4 failing to return a `secret_id`.

## Subtickets (ordered, dependency-aware)

1. **Resolve the policy-home fork (blocks the rest).** Decide Q1: does the
   scoped `deploy` Nomad ACL policy live in Terraform (`nomad_acl_policy`,
   deployer-owned, matching the "Terraform owns the role + policy"
   decision) or in Ansible (a `*.hcl` file applied like
   `developer`)? Record it. Exactly one home.
2. **Ansible: enable + configure the Nomad secrets engine.** Add
   idempotent tasks after `tasks/main.yml:187` mirroring the
   check-then-enable pattern at lines 198-214: `vault secrets enable
   nomad`, then write `nomad/config/access` with the `nomad_bootstrap_token`
   fact (162-164) and the Nomad address. Verify evals 1-2.
3. **Terraform: add the `deploy` role (+ policy per Q1).** In
   `deployments/infrastructure`, add `vault_nomad_secret_role` "deploy"
   with `policies = ["deploy"]` and the short `ttl`/`max_ttl`, plus the
   scoped Nomad ACL policy if Q1 chose Terraform. `just pre_commit` green.
4. **Run the live evals**, including the eval 6 negative-capability proof,
   and record the transcript. Confirm eval 7 (`developer` untouched).
5. **Run the adversarial review** (`.claude/rules/adversarial-reviews.md`)
   and act on its verdict.

## Open questions (forks the operator must settle)

- **Q1 — Where does the scoped `deploy` Nomad ACL policy live: Terraform
  or Ansible?** The resolved config-split decision says "Terraform owns
  the `deploy` role and the scoped Nomad ACL policy." Authoring the policy
  as a Terraform `nomad_acl_policy` (the `hashicorp/nomad ~>2.5.0`
  provider is already in the `infrastructure` root,
  `providers.tf:3-6`) keeps role and policy in one deployer-owned place
  and honors that decision literally. The alternative — an Ansible `*.hcl`
  applied like `developer` (`tasks/main.yml:174-187`) — keeps all Nomad
  policies in one Ansible directory but splits ownership and risks the
  deployer's Terraform not being the source of truth for a policy it
  depends on. **Recommendation: Terraform `nomad_acl_policy`,** matching
  the resolved decision and keeping the `deploy` role and its policy
  co-located and deployer-owned. Only fall back to Ansible if the
  deployer's own token cannot yet write Nomad ACL policies at apply time
  (a bootstrap-ordering concern to confirm on the live cluster).
- **Q2 — Exact TTL values within the ~30-60 min band.** The decision is a
  short lease with auto-renew. **Recommendation:** `ttl = "30m"`,
  `max_ttl = "1h"` on the `vault_nomad_secret_role`, so a normal
  `terraform apply` fits inside one lease and a long run auto-renews up to
  an hour before forcing re-auth. Adjust only if a real apply is observed
  to exceed it.
- **Q3 — Which existing job does eval 5's positive `nomad job plan` use?**
  Any `nomad_job` this repo deploys works. **Recommendation:**
  `deployments/infrastructure/services/minio.hcl` (an existing infra job
  in the same root), so the positive check exercises exactly the
  submit-path F8 will rely on. Confirm the file path against the live
  repo at eval time.
- **Q4 — Does the deployer's Vault token have `nomad/config/access` write
  and `nomad/role/*` create rights, or only read on `nomad/creds/deploy`?**
  F5 assumes Ansible (bootstrap Vault root) writes the engine config and
  the Terraform deployer manages the role/policy. If the deployer's Vault
  token is not yet policy-authorized to create the `nomad/role/deploy`
  role, that Vault policy grant is a prerequisite. **Recommendation:**
  confirm the deployer's Vault policy allows create/update on
  `nomad/role/deploy` (and, per Q1, `nomad_acl_policy` writes); if not,
  add that grant as the first Terraform/Ansible step. This is the same
  class of prerequisite F6 will hit for Consul; solve it once, mirror it.
