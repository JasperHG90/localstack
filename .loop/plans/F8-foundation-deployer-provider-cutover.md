---
epic = "foundation"
depends_on = ["F5-foundation-vault-nomad-secrets-engine", "F6-foundation-vault-consul-secrets-engine", "F11-foundation-human-read-role", "A1-audit-plan-premise-sweep"]
priority = 40
summary = "Flip the Nomad and Consul Terraform providers off their static god-mode env tokens onto Vault-brokered short-lived tokens, then delete the static tokens so the F7 OIDC session is the only credential entry point. Highest blast radius of the F5-F8 sub-feature: the Consul state backend consumes a token at init, before any provider runs."
tags = ["vault", "nomad", "consul", "terraform", "secrets"]
---

# F8 — Deployer Terraform provider cutover: static god-mode tokens → Vault-brokered dynamic tokens (foundation)

## Title
Flip the privileged deployer's Nomad and Consul Terraform providers off
the three static god-mode env tokens (`NOMAD_TOKEN`, `CONSUL_TOKEN`, root
`VAULT_TOKEN`) and onto short-lived tokens brokered by Vault
(`nomad/creds/deploy`, `consul/creds/deploy` from F5/F6), mirroring how the
MinIO and Postgres providers already pull admin creds from Vault, then
delete the static tokens so the operator's F7 OIDC Vault session is the only
credential entry point.

## Size / Effort
**Large.** The line count is small (two `providers.tf` files, two
`justfile`s, one `.env.example`), but this is the highest-blast-radius
ticket of the F5–F8 sub-feature and carries three hard subtleties, each of
which can lock the operator out of running Terraform at all:

1. **The Consul state backend consumes a token at `init` time, before any
   provider or ephemeral resource runs.** Both roots use
   `backend "consul" {}` (`deployments/applications/backend.tf:1-3`,
   `deployments/infrastructure/backend.tf:1-3`) and the justfiles feed it
   `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` on every `init`/`apply`/`destroy`
   (`deployments/applications/justfile:10,14,18`,
   `deployments/infrastructure/justfile:8,12,16`). A Vault-brokered token
   read inside the config cannot cover the backend, because the backend is
   configured before Terraform evaluates the graph. This is the load-bearing
   design fork (Q1).
2. **Nomad and Consul are not symmetric in the `hashicorp/vault ~>5.3.0`
   provider.** Nomad has a first-class token-issuing data source
   (`vault_nomad_access_token`, backing `/nomad/creds/{role}` — confirmed in
   the pinned provider binary). Consul has **no** equivalent
   `vault_consul_access_token`; only `vault_consul_secret_backend` and
   `vault_consul_secret_backend_role` are management resources. Reading a
   brokered Consul token therefore needs a generic read
   (`vault_generic_secret` against `consul/creds/deploy`), a different shape
   from the Nomad read. This is Q2.
3. **Terraform's provider config is not re-read mid-apply.** Brokered tokens
   are short-lived (owned by F5/F6). A token minted at graph-eval must
   outlive the whole apply. Whether the read must be an `ephemeral` resource
   (Terraform 1.12.2 is present, so ephemerals are available and the repo
   already uses `ephemeral "vault_kv_secret_v2"`) or a plain `data` source,
   and what TTL the F5/F6 roles must grant, is Q3.

Effort is Large because of the required *proof gate*: a dry
`terraform init` + `terraform plan` must succeed on both roots against
brokered tokens **before** the static tokens are deleted, and a revertible
rollback must be kept. It is not the diff that is large; it is the
verification and the failure cost.

## Triggered by
The localstack home-lab **auth epic**, F5–F8 sub-feature. Today the
privileged Terraform deployer authenticates to Vault, Nomad, and Consul with
three static god-mode tokens read from `.devcontainer/.env`:
`NOMAD_TOKEN`, `CONSUL_TOKEN`, and a root `VAULT_TOKEN`
(`.devcontainer/.env.example:2,6,10`). The sub-feature replaces these with
Vault-brokered, scoped, short-lived tokens. F5 stands up the Vault Nomad
secrets engine (`nomad/creds/deploy`), F6 the Vault Consul secrets engine
(`consul/creds/deploy`), F7 the operator's Vault OIDC login plus the scoped
`deployer` policy. **F8 is the cutover** — the last ticket of the four — that
flips the providers and removes the static tokens.

## Context (today's state)
The correct pattern already exists in this repo for two of the five
providers; F8 extends it to the remaining two and removes the static path.

- **The pattern to mirror already ships.** In the `applications` root, the
  MinIO and Postgres providers read their admin creds from Vault via
  ephemeral resources: `provider "minio"` and `provider "postgresql"` at
  `deployments/applications/providers.tf:40-53` consume
  `ephemeral.vault_kv_secret_v2.minio_admin` and `.postgres_admin`, which are
  declared at `deployments/applications/services.tf:11-19` against
  `var.secret_mount`. Nomad and Consul must adopt the same broker-from-Vault
  shape (though from the F5/F6 *creds* engines, not KV — see §Requirements).
- **The two providers still on static env tokens (applications root).**
  `provider "nomad" {}` (empty — reads `NOMAD_TOKEN`/`NOMAD_ADDR` from env)
  at `deployments/applications/providers.tf:30`, and `provider "consul"` at
  `deployments/applications/providers.tf:34-38` (sets `address`/`datacenter`
  in-block but reads its token from `CONSUL_HTTP_TOKEN` env, per the inline
  comment at line 35 that the address is *not* read from env).
- **The two providers still on static env tokens (infrastructure root).**
  `provider "nomad" {}` at `deployments/infrastructure/providers.tf:26` and
  `provider "vault" {}` at `deployments/infrastructure/providers.tf:28`. Note
  the infrastructure root has **no active `consul` provider** — the `consul`
  provider is commented out in `required_providers`
  (`deployments/infrastructure/providers.tf:19-22`). Consul enters this root
  only as the **state backend**, not as a provider. That distinction is the
  crux of Q1 for this root.
- **The Consul state backend is configured at init, credentialed by env.**
  Both roots declare `terraform { backend "consul" {} }`
  (`deployments/applications/backend.tf:1-3`,
  `deployments/infrastructure/backend.tf:1-3`), initialized with
  `-backend-config=./vars/backend-config.hcl`
  (`deployments/applications/vars/backend-config.hcl`,
  `deployments/infrastructure/vars/backend-config.hcl` — each sets
  `address = "192.168.2.30:8500"`, a `path`, `scheme = "http"`, but **no
  token**). The token comes from the `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}`
  prefix on the justfile recipes. The backend runs before the provider
  graph, so a graph-level Vault read cannot feed it.
- **`vault provider {}` (applications root) inherits the operator's
  session.** `provider "vault" {}` at
  `deployments/applications/providers.tf:32` and
  `deployments/infrastructure/providers.tf:28` are empty, so they read
  `VAULT_ADDR`/`VAULT_TOKEN` from the environment. After F7, that token is
  the operator's OIDC-derived session token from `vault login`, not the
  static root token — this is the single authenticated entry point the
  cutover leaves standing.
- **The static tokens the cutover removes.** `.devcontainer/.env.example`
  lists `NOMAD_TOKEN` (line 2), `CONSUL_HTTP_TOKEN` (line 6), root
  `VAULT_TOKEN` (line 10). The live `.devcontainer/.env` additionally uses
  the var name `CONSUL_TOKEN` (referenced as `${CONSUL_TOKEN}` in every
  justfile). All three static god-mode tokens must go; `NOMAD_ADDR`,
  `CONSUL_HTTP_ADDR`, `VAULT_ADDR`, and the Vault unseal keys are addresses/
  operational secrets, not deployer god-tokens — they stay (Q4 confirms
  scope).
- **The provider set is pinned.** `hashicorp/nomad ~>2.5.0`,
  `hashicorp/vault ~>5.3.0`, `hashicorp/consul ~>2.22.0`
  (`deployments/applications/providers.tf:1-27`). Terraform is v1.12.2
  (ephemeral resources supported). The vault provider binary confirms
  `vault_nomad_access_token` and `vault_generic_secret` exist; no
  `vault_consul_access_token` exists.
- **The offline validate gate never touches the backend.** `just pre_commit`
  runs `scripts/tf_validate.sh`, which validates each root with
  `init -backend=false` and no credentials, so `terraform validate` will
  pass the new provider wiring **without** proving the live backend/creds
  path. That means the live `just apply` reconcile in §8 is the only gate
  that exercises the real cutover; the offline gate is necessary but not
  sufficient here.

## Non-goals / out of scope
- **Creating the secrets engines or the OIDC login.** F5 (`nomad/creds/deploy`),
  F6 (`consul/creds/deploy`), and F7 (operator OIDC + `deployer` policy) are
  their own tickets. F8 consumes their outputs and must not re-implement
  them. F8 **cannot land until F5, F6, and F7 exist** (see §Dependencies).
- **CI / GitHub Actions auth.** Explicitly deferred. This cutover targets the
  local devcontainer path only (Q4-resolved). Do not touch
  `C1-cicd-tailscale-github-actions-deploy` or add any CI credential path.
- **Re-architecting the MinIO/Postgres providers.** They already broker from
  Vault correctly (`deployments/applications/providers.tf:40-53`). Only match
  their pattern for Nomad/Consul; do not rewrite them (CLAUDE.md "Surgical
  Changes").
- **Retiring the broad `developer` Nomad policy.** The permissive
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl` (namespace
  `write` + `host_volume "*" write`) becomes dead once nothing uses the
  static Nomad token, but retiring it is downstream cleanup, not this ticket.
  Note it in §Subtickets as a follow-on; do not delete it here unless the
  live reconcile proves nothing else depends on it.
- **Rotating or revoking the existing live tokens in Vault.** F8 removes them
  from the repo's `.env.example` and justfiles; operationally revoking the
  old root/bootstrap tokens is a manual operator step flagged in §Risk, not
  code.

## Requirements & restrictions
1. **Broker Nomad and Consul provider tokens from Vault, not env.** Rework
   the `nomad` and `consul` providers in
   `deployments/applications/providers.tf` and the `nomad` provider in
   `deployments/infrastructure/providers.tf` so their `token` comes from a
   Vault read of the F5/F6 creds paths, set explicitly in the provider block,
   mirroring how `provider "minio"`/`provider "postgresql"` set creds from
   `ephemeral.vault_kv_secret_v2.*`
   (`deployments/applications/providers.tf:40-53`). The `vault` provider stays
   empty (`{}`) and inherits the operator's F7 OIDC `VAULT_TOKEN` — it is the
   only directly-authenticated provider.
2. **Use the correct read shape per engine (they differ — Q2).** For Nomad,
   use the first-class `vault_nomad_access_token` data source (or its
   ephemeral equivalent if one exists — Q3) against the F5 role
   (`nomad/creds/deploy`). For Consul, there is no `vault_consul_access_token`;
   use `vault_generic_secret` (or ephemeral generic read — Q3) against
   `consul/creds/deploy` and pull `.data["token"]` from the F6 engine's
   response. Confirm the exact response attribute names against the F6 ticket
   before wiring (Q2).
3. **Solve the backend-at-init credential problem without reintroducing a
   god-token (Q1).** The `consul` state backend is configured before the
   provider graph, so it cannot read a brokered token from within the config.
   The cutover MUST keep `terraform init`/state access working. Investigate
   and adopt the minimal in-repo option (recommendation in Q1): keep the
   justfile recipes minting a **scoped, short-lived** Consul token for the
   backend at init time by reading `consul/creds/deploy` via the operator's
   Vault session (`vault read -field=token consul/creds/deploy`) and exporting
   it as `CONSUL_HTTP_TOKEN`, rather than passing the static `${CONSUL_TOKEN}`.
   This keeps the entry point Vault-only while satisfying the pre-provider
   backend. Do not leave the static `${CONSUL_TOKEN}` path in place.
4. **Guarantee the brokered token outlives a full apply (Q3).** Because
   Terraform does not re-read provider config mid-apply, the F5/F6 roles must
   grant a lease long enough for a full `just apply` on the larger
   (`applications`) root. If the provider model cannot auto-renew a token
   mid-apply, treat that as a real constraint: specify the minimal handling
   (a lease sized for a full apply) as a requirement handed back to F5/F6, and
   record it in Q3 — do not silently assume renewal works.
5. **Remove all three static god-mode tokens.** Delete `NOMAD_TOKEN`,
   `CONSUL_HTTP_TOKEN`/`CONSUL_TOKEN`, and root `VAULT_TOKEN` from
   `.devcontainer/.env.example` (`.env.example:2,6,10`) and drop the
   `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` prefixes from both justfiles
   (`deployments/applications/justfile:10,14,18`,
   `deployments/infrastructure/justfile:8,12,16`), replacing them per
   Requirement 3. Keep `NOMAD_ADDR`, `CONSUL_HTTP_ADDR`, `VAULT_ADDR`, and the
   Vault unseal keys (addresses/operational secrets, not deployer god-tokens).
6. **Keep a tested, revertible rollback (CLAUDE.md "Think Before Coding" +
   §Risk).** Do not delete the static-token path until the dry
   `init`+`plan` proof (§8) passes on both roots. The revert is the git diff
   of this ticket; state that the previous env-token justfile recipes are the
   documented fallback if the brokered path fails.
7. **Respect repo principles, each cited:** "Simplicity First" and "Surgical
   Changes" (CLAUDE.md) — touch only the files in §7, do not "improve"
   adjacent provider blocks. Secrets convention (CLAUDE.md "Key Conventions":
   *All in Vault KV2. Never hardcode credentials*) — the whole point of the
   cutover; no token literal may appear in any tracked file. Adversarial
   review before done (`.claude/rules/adversarial-reviews.md`). If any
   markdown doc is edited, the doc slop gates apply
   (`.claude/rules/slop-scan-for-docs.md`).
8. **Prove a FULL `terraform apply` of the infrastructure root under the
   minted `deploy` token (relayed from F5).** F5 only proved that a
   `nomad/creds/deploy` token can `nomad job plan` (submit-job) and *read*
   the 8 `nomad_dynamic_host_volume` resources (`nomad volume status -type
   host` lists them) — it never ran a full apply. When Requirement 1 rewires
   `deployments/infrastructure/providers.tf`'s `nomad` provider to
   `nomad/creds/deploy`, the acceptance for that root MUST include a real
   `terraform apply` (or at minimum a `plan` that touches every resource
   kind, then an apply of a no-op change) that exercises the
   `nomad_dynamic_host_volume` create/update/delete path, not just job
   submission. The `deploy` policy grants the namespace caps
   `host-volume-create/register/read/write/delete`; two of them
   (`host-volume-register`, `host-volume-write`) are granted but NOT
   exercised by the current create-only volume resources. If this apply
   proof passes without them, a least-privilege follow-up may trim
   `register`/`write` from the F5 policy — but confirm against a real apply
   first, and do not trim if the apply needs them. Do not widen the policy
   beyond what the apply actually requires.
9. **Fix the inert Consul state-lock session grant before running the
   deployer against the brokered Consul token (relayed from F6).** F6's
   `deploy` Consul ACL policy (`bootstrap/playbooks/enable_consul_secrets.yml`)
   grants `session_prefix "terraform/" { policy = "write" }`, which is INERT:
   Consul session ACLs match on the NODE NAME a session binds to, not a KV
   path prefix (see `bootstrap/roles/consul_server/files/agent_policy.hcl`,
   which pairs `session_prefix ""` with `node_prefix ""`). Terraform's Consul
   state backend acquires a lock SESSION bound to the local Consul agent node,
   so under the current rule the brokered `deploy` token cannot create that
   session and state locking will silently fail the moment this ticket points
   the provider/backend at `vault read consul/creds/deploy`. Change the grant
   to `session_prefix "" { policy = "write" }` (minimal working form, matching
   `agent_policy.hcl`) and VERIFY it live: F6 eval 5 is a raw `consul kv
   put/get` with no `-lock`, so it never exercised locking — run an actual
   state-locking cycle (a real `terraform apply`, or `consul kv put -lock`
   under the brokered token) as part of this ticket's acceptance. This is a
   mis-formed F6 Q6 assumption, not an F6 defect; F6's own DoD was met.

## Code surface
- **`deployments/applications/providers.tf`** — rework `provider "nomad" {}`
  (line 30) to set `token = <Nomad brokered read>` and `provider "consul"`
  (lines 34-38) to set `token = <Consul brokered read>`, keeping the existing
  `address`/`datacenter` on the consul block. Do not touch the `minio`/
  `postgresql`/`vault` blocks (lines 32, 40-53).
- **`deployments/applications/services.tf`** — declare the Vault read
  resources feeding the two providers, alongside the existing
  `ephemeral "vault_kv_secret_v2"` blocks (lines 11-19): a Nomad token read
  (`vault_nomad_access_token` / ephemeral equivalent against
  `nomad/creds/deploy`) and a Consul token read (`vault_generic_secret` /
  ephemeral generic against `consul/creds/deploy`). This is the home for the
  new resources referenced by the provider blocks above.
- **`deployments/infrastructure/providers.tf`** — rework `provider "nomad" {}`
  (line 26) to set its `token` from a Vault Nomad-creds read; leave
  `provider "vault" {}` (line 28) empty (inherits F7 OIDC token) and the
  `google` provider (lines 30-32) untouched. Add the matching Vault read
  resource for this root (there is no `services.tf` split here for it — place
  it in a root `.tf`; confirm the conventional file, e.g. alongside
  `secrets.tf`, during implementation).
- **`deployments/applications/justfile`** — replace the three
  `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` prefixes (lines 10, 14, 18) with a
  Vault-brokered backend-token export per Requirement 3 (init needs it; apply/
  destroy need it for backend state access too).
- **`deployments/infrastructure/justfile`** — same replacement on lines 8, 12,
  16.
- **`.devcontainer/.env.example`** — remove `NOMAD_TOKEN` (line 2),
  `CONSUL_HTTP_TOKEN` (line 6), root `VAULT_TOKEN` (line 10). Keep the address
  and unseal-key lines. If the file carries an explanatory comment block, add
  a one-line note that deployer tokens now come from `vault login` (F7); that
  edit makes this a markdown-adjacent `.env` — no slop gate (it is not `.md`),
  but keep it terse.
- **(No new test file — see §8.)** This root has no Python/pytest surface;
  the acceptance gate is the live reconcile + the offline validate gate, not a
  unit test. Every "test" named in §8 is a live cluster check or a repo grep,
  so it has no source-tree home to declare beyond the files above.

## Tests & validation gates
This is Terraform/HCL and shell (justfiles) with no Python and no `pytest`
surface, so the reproducing-test rule in `.claude/rules/python-testing.md`
does not bind (there is nothing to unit-test). The binding gates are the
repo's configured loop gate plus the live reconcile below, and the
adversarial review (`.claude/rules/adversarial-reviews.md`).

### Repo gate (must be green before the live apply)
The single configured loop gate is **`just pre_commit`** (`.loop/config.json`
`gates`), which runs `pre-commit run --all-files` (root `justfile:17-18`).
The hooks that touch this change, from `.pre-commit-config.yaml`:
- `terraform-fmt` (`terraform fmt -check -recursive`) — both `providers.tf`
  edits and any new `.tf` must be formatted. Run `terraform fmt` first.
- `terraform-validate` (`scripts/tf_validate.sh`) — validates
  `deployments/applications` and `deployments/infrastructure` **offline**
  (`init -backend=false`, no creds). This proves the new provider/data wiring
  parses and type-checks but does **not** exercise the live backend or Vault
  reads. Necessary, not sufficient.
- `check-yaml` / `end-of-file-fixer` — any YAML/text touched.
The `.pre-commit-config.yaml` `exclude: '^\.(claude|loop)/'` means the ticket
and eval files are not linted.

### Dry proof gate (MUST pass before deleting the static tokens — Q6/§Risk)
Run against the live cluster with the operator's F7 Vault session active
(`vault login` done), on BOTH roots, using the NEW brokered path but with the
static tokens still revertible in git:
1. **`terraform init` succeeds against the Consul backend with a brokered
   backend token** (not `${CONSUL_TOKEN}`) — proves Q1's solution works and
   state is reachable.
2. **`terraform plan` succeeds** on each root — proves the brokered Nomad/
   Consul provider tokens authenticate and the graph reads clean (no auth
   error, no perpetual diff introduced by the rewrite).
Only after both roots pass 1+2 do you remove the static tokens.

### Live reconcile (close-out acceptance, after the static tokens are removed)
1. **`just apply` reconciles cleanly on `deployments/infrastructure`** using
   only the brokered path — exit 0, no unexpected diff, no auth error.
2. **`just apply` reconciles cleanly on `deployments/applications`** using
   only the brokered path — exit 0, no unexpected diff, no auth error. This is
   the larger root and the one whose full-apply duration bounds the required
   token lease (Q3).
3. **No static privileged token remains in the repo.**
   `git grep -nE 'NOMAD_TOKEN|CONSUL_HTTP_TOKEN|CONSUL_TOKEN|VAULT_TOKEN'`
   over tracked files returns only intended references (address/comment lines,
   never a god-token binding). Specifically, `.env.example` and both justfiles
   no longer bind these to a static value.
4. **The `vault` provider is the only directly-authenticated provider** — a
   grep of both `providers.tf` shows `nomad` and `consul` provider `token`
   fields sourced from Vault reads, and `provider "vault"` still `{}`.

### Eval marker
Encode the dry-proof gate, the two-root reconcile, and the no-static-token
grep as the Definition-of-Done marker at
`.loop/evals/F8-foundation-deployer-provider-cutover.md` (co-author it with
the `create-eval` skill before implementation). `.loop/config.json` sets
`require_eval: true`, so the loop refuses pickup until this marker exists.

## Risk assessment
- **Blast radius — highest of the four sub-feature tickets.** A botched
  provider or backend cutover can lock the operator out of running Terraform
  **entirely**: a bad backend-token change breaks `terraform init` (no state
  access — cannot plan, cannot apply, cannot roll forward through Terraform),
  and a bad provider-token change breaks every `nomad_job`/`consul_*`/`minio`/
  `postgresql` resource in both roots. This governs the whole home lab's
  infra + application layer.
- **Reversibility — high but only if sequenced correctly.** The revert is the
  git diff of this ticket; the previous env-token justfile recipes are the
  fallback. Reversibility holds **only** because Requirement 6 forbids
  deleting the static path until the dry `init`+`plan` proof passes. If the
  static tokens are removed before the proof, and the brokered path is wrong,
  recovery requires hand-editing tokens back into `.env` from Vault/backups —
  painful, not automatic. Sequence is load-bearing.
- **Likeliest failure modes:**
  1. **Backend `init` loses its token (Q1).** Dropping `${CONSUL_TOKEN}`
     without a brokered replacement → `init` fails to reach Consul state.
     Caught by dry-proof step 1.
  2. **Consul read shape wrong (Q2).** Wiring a non-existent
     `vault_consul_access_token`, or reading the wrong response attribute →
     `plan` fails or the consul provider gets an empty token. Caught by
     dry-proof step 2.
  3. **Brokered token expires mid-apply (Q3).** F5/F6 lease too short for the
     `applications` full apply → auth error partway through. Caught by live
     reconcile step 2; mitigated by the lease-sizing requirement handed to
     F5/F6.
  4. **Ordering: F8 lands before F5/F6/F7.** The creds paths or OIDC policy
     don't exist yet → nothing works. Prevented by the dependency gate
     (§Dependencies); do not pick F8 up until F5+F6+F7 are done.
  5. **A residual static token stays behind.** e.g. `.env` (untracked) still
     works locally, masking a broken `.env.example`/justfile for the next
     operator. Caught by live reconcile step 3's git-grep and by running the
     apply from a shell where the static vars are unset.
- **Operational note (not code):** revoking the old root/bootstrap tokens in
  Vault after cutover is a manual operator action, flagged here so it is not
  forgotten; it is out of this ticket's code scope.

## Subtickets (ordered, dependency-aware)
1. **Confirm F5/F6/F7 outputs exist and read their contracts.** Verify
   `nomad/creds/deploy`, `consul/creds/deploy`, and the operator OIDC
   `deployer` policy are live, and note the exact Consul creds response
   attribute (Q2) and the granted lease TTLs (Q3). This is a hard gate — do
   not start wiring until these are real.
2. **Wire the brokered reads + providers (applications root).** Add the Nomad
   token read and Consul token read to
   `deployments/applications/services.tf`, set the `token` on the `nomad` and
   `consul` provider blocks in `deployments/applications/providers.tf`. Run
   `terraform fmt` + `scripts/tf_validate.sh`.
3. **Wire the brokered read + provider (infrastructure root).** Add the Nomad
   token read and set the `token` on `provider "nomad"` in
   `deployments/infrastructure/providers.tf`. Format + validate.
4. **Solve the backend-init token (Q1) in both justfiles.** Replace
   `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` with a Vault-brokered backend-token
   export on `init`/`apply`/`destroy` in both justfiles.
5. **Dry-proof on both roots.** With static tokens still present in git, run
   `terraform init` + `terraform plan` on each root via the new brokered path.
   Both must pass before proceeding.
6. **Remove the static tokens.** Delete `NOMAD_TOKEN`, `CONSUL_HTTP_TOKEN`,
   root `VAULT_TOKEN` from `.devcontainer/.env.example`; confirm no justfile
   or `.tf` binds them. Run the no-static-token git-grep.
7. **Live reconcile + adversarial review.** `just apply` on
   `deployments/infrastructure` then `deployments/applications` from a shell
   with the static vars unset; confirm clean reconcile; run the adversarial
   review.
8. **(Follow-on, not necessarily here) Retire the broad `developer` Nomad
   policy** (`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`)
   once the live reconcile proves nothing else uses the static Nomad token.
   Track as downstream cleanup.

## Dependencies / cross-refs
- **F8 DEPENDS ON F5, F6, AND F7.** It is the last ticket of the F5–F8
  sub-feature and cannot land until the Vault Nomad secrets engine
  (`nomad/creds/deploy`, F5), the Vault Consul secrets engine
  (`consul/creds/deploy`, F6), and the operator OIDC login + scoped `deployer`
  policy (F7) all exist. As of writing, no `F5`/`F6`/`F7` plan files exist in
  `.loop/plans/` — they must be authored and completed first. Do not pick F8
  up until then.
- **Downstream cleanup:** retiring
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl` (§Subtickets
  step 8), once nothing uses the static Nomad token.
- **CI (deferred):** `C1-cicd-tailscale-github-actions-deploy` will need its
  own non-interactive Vault auth path (e.g. JWT/AppRole) since it has no
  operator OIDC session — explicitly out of F8's scope.

## Resolved decisions (operator-settled — do NOT re-open)
- **Operator auth = Vault OIDC (F7).** Terraform inherits the operator's
  `VAULT_TOKEN` from `vault login`; every other provider token derives from
  Vault. Only `provider "vault"` is authenticated directly; Nomad and Consul
  are brokered.
- **CI is out of scope (deferred).** This cutover targets the local
  devcontainer path only.
- **Brokered creds are short-lived + auto-renew (owned by F5/F6).** F8 must
  surface, not silently swallow, any Terraform-provider limitation on
  mid-apply renewal (Q3), but does not own the engine/lease design.

## Open questions
- **Q1 — How does the Consul state backend get a token once `${CONSUL_TOKEN}`
  is gone?** The backend is configured at `init`, before the provider graph,
  so no in-config Vault read can feed it.
  **Recommendation:** have the justfile recipes mint a scoped, short-lived
  Consul token from the operator's Vault session at invocation time
  (`export CONSUL_HTTP_TOKEN=$(vault read -field=token consul/creds/deploy)`)
  and prefix `init`/`apply`/`destroy` with it. This keeps the entry point
  Vault-only, needs no static token, and requires F6's `consul/creds/deploy`
  to grant a Consul token with `terraform/*` KV read/write on the state path.
  Confirm the F6 role scopes state-path access.
- **Q2 — Exact Consul brokered-read shape.** The `hashicorp/vault ~>5.3.0`
  provider has `vault_nomad_access_token` (Nomad) but NO
  `vault_consul_access_token`. The Consul token must come from a generic read
  of `consul/creds/deploy`.
  **Recommendation:** use `vault_generic_secret` (or its ephemeral variant per
  Q3) and read the token attribute the F6 Consul engine returns (typically
  `.data["token"]`). Verify the exact attribute name against the F6 ticket
  before wiring — do not guess.
- **Q3 — Ephemeral vs data source, and required lease TTL.** Terraform is
  v1.12.2 and the repo already uses `ephemeral "vault_kv_secret_v2"`, so
  ephemeral resources are available and are the privacy-preferred shape (no
  token in state). But `vault_nomad_access_token`/`vault_generic_secret` may
  only be plain `data` sources in this provider version, which would write the
  token to state.
  **Recommendation:** prefer ephemeral reads if the provider exposes them for
  these paths; if only `data` sources exist, accept the state write for now
  (state is in the private Consul backend) and flag it. Separately, the F5/F6
  roles must grant a token lease longer than a full `applications`
  `just apply`; measure that duration during the dry proof and hand the number
  to F5/F6. If Terraform cannot renew mid-apply, a lease sized to the longest
  apply is the minimal handling.
- **Q4 — Which env vars are god-tokens vs operational?** Resolved by scope:
  remove `NOMAD_TOKEN`, `CONSUL_HTTP_TOKEN`/`CONSUL_TOKEN`, root `VAULT_TOKEN`;
  keep `NOMAD_ADDR`, `CONSUL_HTTP_ADDR`, `VAULT_ADDR`, and the Vault unseal
  keys (addresses and unseal material are not deployer credentials). No
  further decision needed — noted for completeness.
- **Q5 — Delete the broad `developer` Nomad policy in F8, or defer?**
  **Recommendation:** defer to a follow-on (§Subtickets step 8). Deleting it
  in F8 widens the blast radius of an already high-risk ticket and risks
  breaking an unrelated consumer; retire it only after the live reconcile
  proves nothing uses the static Nomad token.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: BROKEN. Gate verdict: `fail`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/F8-foundation-deployer-provider-cutover.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: Acceptance is unachievable under the grant its dependency F7 declares, and the brokered token cannot manage the Nomad ACL policy that defines it. Two eval rows are `git grep` guardrails that pass against wrong content.

This ticket is **`blocked`** (`unresolved-design-fork`). A1 applied no
structural fix here: the required fixes reverse design decisions or need an
operator call. **Do not implement from this plan as written.** Work the
verdict's required-fix list, then re-dispatch `loop-plan-reviewer` before
unblocking.

# REPLANNED, 2026-07-31

**This section supersedes every conflicting statement above.** The
plan-validator listed nine required fixes and named P1 as a design question
the plan did not contain at all. Both P1 and P2 are answered below, from a
precedent already in the repo.

## P2 first, because it unlocks P1

**The problem.** `nomad_acl_policy.deploy`
(`deployments/infrastructure/nomad_deploy_role.tf:13`) is a Terraform
resource. Writing a Nomad ACL policy requires a **management** token. The
brokered `nomad/creds/deploy` token is `type: client`
(`nomad_deploy_role.tf:39`, confirmed live: `nomad acl token self` reports
`Type = client`). So the deployer can never apply the very policy that defines
it. Requirement 8's "full apply" proof was unrunnable, exactly as the verdict
said.

**The answer, and it is not new machinery.** Ansible already authors a Nomad
ACL policy with the management token:

```
bootstrap/roles/nomad_server/tasks/main.yml:182-184
  nomad acl policy apply -description "Developer policy" developer \
    /opt/nomad/policies/nomad_developer_policy.hcl
  env: NOMAD_TOKEN={{ nomad_bootstrap_token }}
```

with the source checked in at
`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`.

**Decision: move `nomad_acl_policy.deploy` out of Terraform and into Ansible,
following that precedent exactly.** Terraform keeps
`vault_nomad_secret_role.deploy`, which references the policy **by name** and
needs no Nomad ACL write. `nomad_deploy_role.tf` loses its
`nomad_acl_policy` resource and keeps the Vault role.

Rejected alternative: broker a `type: management` Nomad token for the deployer.
The Vault Nomad secrets engine supports it, and it would make the Terraform
resource applicable. But it hands the deployer god-mode on Nomad, which is the
opposite of what F7 exists to establish, and it would make the `deploy` ACL
policy decorative.

**Two things changed on 2026-08-02, neither of which overturns the decision
above — recorded so the next reader re-decides on facts rather than
re-deriving.** First, the mechanism was measured working: a
`vault_nomad_secret_role` with `type = "management"` mints a token that writes
Nomad ACL objects, and a reviewer confirmed offline that a
resource-to-data-source-to-aliased-provider chain plans clean on empty state
with no two-phase apply. So "it would make the Terraform resource applicable"
is now demonstrated, not assumed. Second, **F7 was retired**, and the
rejection's main reason is stated in terms of what F7 exists to establish. The
security objection still stands on its own — brokering a management token
hands anyone who runs `localstack login` god-mode on Nomad — but the sentence
carrying it now cites a ticket that no longer exists, so it needs rewriting
either way. G2 takes the management-role route for its own two ACL resources
and states that cost in its risk section; F8 is free to decide differently for
`nomad_acl_policy.deploy`.

Consequence for the config-split invariant this repo already follows: the
thing that needs a management token lives with the thing that holds one.
Consul's `deploy` policy is already Ansible-side for the same reason
(`consul_deploy_role.tf:7-15` says so explicitly). This makes Nomad consistent
with Consul rather than introducing a new split.

## P1 — the five infra-root Vault objects

**The problem.** F8 asserted "the F7 OIDC session is the only credential entry
point" and that `just apply` of the infrastructure root succeeds under it. F7's
policy, as originally written, forbade `sys/*` and `auth/*`, which that root
writes. The fork was in neither plan.

**The answer shipped — as F11, not F7. Corrected 2026-08-02.** This section
was written against F7's replan. **F7 is retired** (`dropped: true`, plan file
deleted) and is not in F8's dependency list, which the ledger gives as `F5`,
`F6`, `F11`, `A1`. The policy it describes exists anyway: `vault_policy.developer`
in `deployments/infrastructure/developer_group.tf`, applied and live since
2026-08-01, grants `sys/mounts/secret`, `sys/auth/userpass` (the one path
needing `sudo`), `sys/policies/acl/*`, `auth/jwt-nomad/role/*`,
`auth/userpass/users/*`, `identity/*`, `nomad/role/*` and `consul/roles/*`.
The least-privilege story is "scoped `sys` and `auth`", not "no `sys` and
`auth`".

Two consequences the old text got wrong. F8's acceptance criterion is
achievable without splitting the infrastructure root — that part stands. But
**it does not need to wait for anything**: the policy is already applied, so
the dependency the old text called load-bearing is satisfied, not pending.
Read every remaining "F7" in this plan as F11 or as stale; F11's own header
says plainly that it is not a containment boundary, which is the caveat F7's
least-privilege framing did not carry.

## Fix 5 — F8 owns the lease TTLs

F5 and F6 are closed, so "hand the number to F5/F6" has nobody to hand it to.
The two live values:

- Nomad: `ttl=30m max_ttl=1h` at
  `bootstrap/roles/nomad_server/tasks/main.yml:309`.
- Consul: `ttl = 1800`, `max_ttl = 3600` at
  `deployments/infrastructure/consul_deploy_role.tf:23-24`.

**Decision: leave both at 30m/1h and make the deployer renew within a run.**
A long `terraform apply` outliving its token is the failure to design for, and
the fix is renewal, not a longer lease. If a real apply is measured to exceed
an hour, that is a finding for a follow-up, not a reason to widen the lease
now. Both files join the code surface.

## Fix 7 — the ephemeral branch is closed, not open

Vault provider 5.3.0 exposes `ephemeral` only for `vault_database_secret` and
`vault_kv_secret_v2`. There is no ephemeral form for the Nomad or Consul creds
endpoints, so **both brokered tokens WILL land in Terraform state**, and that
state travels to the Consul backend. State this as settled.

Two consequences worth carrying rather than hiding:

- Terraform state already holds every secret this repo writes, so the brokered
  tokens are not a new class of exposure. They are, however, short-lived, which
  the static tokens they replace were not.
- `N4-netsec-edge-only-service-access` moves the Consul backend address to the
  HTTPS edge. Until then the state travels over plaintext HTTP. That is a real
  interaction between these two tickets and belongs in F8's risk section.

## Fixes 3, 4, 6, 9 — anchors and stale facts

Re-anchor at pickup rather than trusting any list written today; these files
moved repeatedly. Known corrections: `deployments/applications/providers.tf` is
`:34`, `:36`, `:38-42`, `:44-57`, and `provider "bifrost"` at `:59-69` must
join the do-not-touch list and the provider count.
`deployments/applications/justfile` has five occurrences at 10, 18, 22, 27, 31.
Add `bootstrap/playbooks/enable_consul_secrets.yml:46-48` for the
`session_prefix` change. Terraform is v1.14.3. Nine dynamic host volumes, not
eight.

## Fix 8 — the eval

Replace the two grep guardrails with checks that fail on wrong content, and
add rows for the host-volume apply and the state-locking cycle. Specifically:

- Assert `git grep -c '\${CONSUL_TOKEN}' -- deployments` returns **0**.
- Assert the resolved provider token paths are `nomad/creds/deploy` and
  `consul/creds/deploy`, not merely that some brokered path is referenced.
- **A full `just apply` of the infrastructure root under the brokered path**,
  including a `nomad_dynamic_host_volume` change, which is the resource class
  the `deploy` policy's host-volume capabilities exist for.
- **A state-locking cycle**: two concurrent applies, one must block and then
  succeed. Consul-backed locking under a brokered token with a 30-minute lease
  is where renewal actually gets exercised.
- **A row that fails if `nomad_acl_policy` is still a Terraform resource**,
  since P2's whole answer is that it moved to Ansible.

## Ordering note

F8 now depends on F7 in substance, not just in the ledger. Do not pick it up
until F7's policy is applied and its own eval rows pass, because F8's
acceptance is "the whole thing works under that policy" and there is nothing to
test against until it exists.
