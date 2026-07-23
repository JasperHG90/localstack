---
depends_on: []
---

# F6: Broker short-lived scoped Consul ACL tokens for the deployer via Vault's Consul secrets engine (foundation)

## Title

Enable Vault's Consul secrets engine and expose a scoped `deploy` role so
`vault read consul/creds/deploy` mints a short-lived, least-privilege
Consul ACL token, replacing the static god-mode Consul bootstrap token the
Terraform deployer authenticates with today. Config split: Ansible enables
and configures the engine (holds the Consul management token); Terraform
owns the `deploy` role and its scoped Consul ACL policy. Foundation for F8
(deployer provider cutover).

## Size / Effort

**Small-to-Medium.** The net-new plumbing is small: one Ansible task block
(mirroring `seed_vault.yml`'s idempotent `vault secrets enable` +
`vault write consul/config/access`) and two Terraform resources
(`vault_consul_secret_backend_role` + the scoped Consul ACL policy). What
drives the effort past trivial is deriving the *minimal* Consul policy from
what the deployer actually touches in Consul (the state backend KV prefix
plus two `consul_service` catalog reads, no more), proving the negative
capability (an out-of-scope Consul write is denied by the brokered token),
and getting the Ansible/Terraform ownership split clean so the two do not
fight over the same Vault mount. F6 does NOT cut the deployer over to the
brokered token; that is F8.

## Triggered by

The localstack auth epic, F5-F8 sub-feature (the privileged Terraform
deployer). Vault is the confirmed identity root (F1 = Nomad WI JWT trust,
F2 = human OIDC). The epic's existing tickets cover humans and in-cluster
workloads but not the third identity class: this repo's deployer, which
provisions Vault/Nomad/Consul and today authenticates to Consul with a
STATIC god-mode bootstrap token. F6 fixes the Consul leg by making Vault
broker short-lived scoped Consul tokens. F5 is the exact-parallel Nomad
version; F6 mirrors its structure.

## Context (today's state)

The deployer authenticates to Consul with a single static, effectively
god-mode token, and Vault has no Consul secrets engine to broker anything
better yet. Concretely:

- **Consul provider auth is a static env token.** The deployer's Consul
  provider hardcodes the address and reads the token from `CONSUL_HTTP_TOKEN`:
  `deployments/applications/providers.tf:34-38`
  (`address = "192.168.2.30:8500"`, `datacenter = "localstack"`; the
  comment on line 35 notes the provider does not read address from env).
- **Every terraform invocation injects that token.** Both roots' justfiles
  export `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` on `init`, `apply`, and
  `destroy`: `deployments/applications/justfile:10,14,18` and
  `deployments/infrastructure/justfile:8,12,16`. The value comes from
  `CONSUL_TOKEN` in `.devcontainer/.env` (real file line 5;
  `deployments/applications/justfile:3` loads that dotenv). Note the
  `.env.example` names the source var `CONSUL_HTTP_TOKEN`
  (`.devcontainer/.env.example:6`) while the real `.env` and the justfiles
  use `CONSUL_TOKEN` — a pre-existing naming skew, called out in Open
  Questions, not fixed here.
- **The static token is the Consul management/bootstrap token.** It
  originates from `consul acl bootstrap` in Ansible, stored at
  `/opt/consul/bootstrap_token`:
  `bootstrap/roles/consul_server/tasks/main.yml:66-99`. This is an
  unscoped global-write token; handing it to the deployer means every
  terraform run holds full Consul ACL power.
- **The Terraform STATE backend is Consul.** Both roots declare
  `backend "consul" {}` (`deployments/infrastructure/backend.tf:2`,
  `deployments/applications/backend.tf:2`) and init against
  `-backend-config=./vars/backend-config.hcl`
  (justfiles line 8/9 and 10/11). The state lives under Consul KV at
  `path = "terraform/infrastructure"`
  (`deployments/infrastructure/vars/backend-config.hcl:2`) and
  `path = "terraform/applications"`
  (`deployments/applications/vars/backend-config.hcl:2`), both at
  `address = "192.168.2.30:8500"`, `scheme = "http"`. The `CONSUL_HTTP_TOKEN`
  gates state-backend access as well as provider calls. Any replacement
  token MUST retain write on the `terraform/` KV prefix or the deployer
  cannot read or persist state.
- **What the deployer actually touches in Consul is small.** Beyond the
  state backend, the only Consul use is two catalog/service reads:
  `data "consul_service" "minio"` (name `minio`) and
  `data "consul_service" "postgres"` (name `postgres-db`),
  `deployments/applications/services.tf:1-9`, consumed for node addresses
  at `providers.tf:41,47` and `services.tf:102,154-155,193-194`. The
  infrastructure root's only Consul-address reference is a rendered
  template value, not a live read: `services.tf:327`
  (`{ consul_address = "192.168.2.30:8500" }`). There are NO
  `consul_key_prefix` / `consul_keys` / `consul_acl_*` managed resources in
  either root (grep of `deployments/**/*.tf`). So the deployer's real Consul
  footprint is: write on the `terraform/` state KV prefix, plus read on the
  `minio` and `postgres-db` service catalog entries (and their nodes).
- **Vault has no Consul engine — greenfield.** The only Vault mount today
  is the KV2 engine (`deployments/infrastructure/secrets.tf:2`,
  `vault_mount "kvv2"` type `kv` v2). No `consul/` or `nomad/` secrets
  engine exists in Ansible or Terraform (grep of `bootstrap/` and
  `deployments/`). The bootstrap-seed precedent for enabling an engine
  idempotently in Ansible is `bootstrap/playbooks/seed_vault.yml:20-28`
  (`vault secrets enable -path=bootstrap kv-v2`, with
  `failed_when: ... 'path is already in use' not in ...stderr`).
- **The vault provider is pinned and available in both roots.**
  `hashicorp/vault ~>5.3.0` (`deployments/infrastructure/providers.tf:7-9`,
  `deployments/applications/providers.tf:7-10`), `provider "vault" {}`
  (both, line 28 / line 32). The 5.3.0 provider binary vendored under
  `deployments/*/.terraform/` exposes the Consul-backend schema (mount
  message "Mounting Consul backend at %q"; role fields `consul_policies`,
  `consul_roles`, `service_identities`, `node_identities`, `max_ttl`,
  `local_ttl`), confirming `vault_consul_secret_backend` and
  `vault_consul_secret_backend_role` resolve against this version.

**What is wrong / missing:**

1. The deployer holds a static, unscoped, god-mode Consul token for its
   entire lifetime. There is no short-lived, least-privilege alternative to
   hand it.
2. Vault cannot broker Consul tokens at all — no Consul secrets engine is
   enabled or configured.
3. There is no scoped `deploy` Consul ACL policy expressing the deployer's
   real footprint (state-KV write + two service reads), so nothing to
   attach a brokered role to.
4. There is no proof, positive or negative, that a brokered token both
   satisfies the deployer's needs and is denied everything else.

## Non-goals / out of scope

- **Not the Nomad secrets engine (F5).** F6 is the Consul-only parallel.
- **Not operator OIDC login (F7).** F6 assumes the operator can already
  reach Vault to run `vault read consul/creds/deploy`; how the operator
  authenticates to Vault is F7.
- **Not the provider cutover (F8).** F6 stands up the engine, role, and
  policy and proves them in isolation. It does NOT change
  `providers.tf`, the justfiles, or `.env` to consume the brokered token.
  The deployer keeps using its static token until F8. Leaving F6's brokered
  path unconsumed is intentional.
- **Not CI / GitHub-Actions auth** (deferred; see C1).
- **Do not rename or re-key the existing Consul bootstrap token** or the
  `CONSUL_TOKEN` env var. The static path must keep working until F8.
- **Do not widen the `deploy` policy** beyond the state-KV prefix and the
  two service reads the deployer demonstrably performs. No management,
  no global write, no `acl = "write"`.
- **Do not fix the `CONSUL_TOKEN` vs `CONSUL_HTTP_TOKEN` `.env.example`
  skew** here (Open Question Q4); it is orthogonal and F8-adjacent.

## Requirements & restrictions

**Must achieve:**

1. **Ansible enables and configures the Consul secrets engine.** A task
   block (in a new or existing bootstrap playbook/role — see Q1) that
   idempotently runs `vault secrets enable -path=consul consul` and
   `vault write consul/config/access address=<consul-addr>
   token=<consul-mgmt-token>`, mirroring the idempotency guard in
   `seed_vault.yml:20-28`. The Consul management token comes from Ansible's
   existing bootstrap-token knowledge
   (`consul_server/tasks/main.yml:66-99`); it is NOT introduced to
   Terraform. The Vault side runs with the Vault root/bootstrap token the
   seed playbook already uses (`seed_vault.yml:11-25`).
2. **Terraform owns the scoped Consul ACL policy and the `deploy` role.**
   A `vault_consul_secret_backend_role "deploy"` (backend `consul`) bound to
   a Consul ACL policy that grants ONLY:
   - `key_prefix "terraform/" { policy = "write" }` — the state backend for
     both roots (`terraform/infrastructure`, `terraform/applications`).
   - `service "minio" { policy = "read" }` and
     `service "postgres-db" { policy = "read" }` (or the minimal
     `service_prefix`/`node` grants the `consul_service` data source needs;
     confirm read vs the catalog surface at apply — see Q3).
   The role sets a short TTL (~30-60 min) and a max TTL, renewable within a
   run (Q2). The role attaches the scoped policy by name via
   `consul_policies` (5.3.0 supports policy-by-name attachment).
3. **A repeatable operator eval proves the brokered token works and is
   scoped.** `vault read consul/creds/deploy` returns a token; that token
   can read the state KV prefix and the two services; and an out-of-scope
   Consul action (e.g. a KV write outside `terraform/`, or any ACL write)
   is DENIED. See Tests & validation gates.

**Config-split invariant (bake in, do NOT re-open):** Ansible does
`secrets enable` + `config/access` (it holds the Consul management token);
Terraform does the `deploy` role + the scoped policy. Terraform must never
need or store the Consul management token — it authenticates to Vault only
(`provider "vault" {}`) and writes role/policy objects. This is why the
engine mount and its `config/access` live in Ansible, not Terraform.

**Repo principles to respect (cited):**

- Secrets live only in Vault; never hardcode credentials
  (`CLAUDE.md`, "Secrets" convention; enforced by `detect-private-key` in
  `.pre-commit-config.yaml`). The Consul management token stays in Ansible's
  existing secret channel; the brokered token is short-lived by design.
- Simplicity first / no speculative scope: the `deploy` policy grants
  exactly the deployer's demonstrated footprint, nothing more
  (`CLAUDE.md` section 2). No extra roles, no wildcard writes.
- Surgical changes; match existing style; do not refactor working code
  (`CLAUDE.md` sections 2-3). The static-token path stays untouched until F8.
- Every change ships with a test / verification
  (`.claude/rules/python-testing.md` `all-code-needs-tests`). This is IaC
  with no Python suite, so the "test" is the operator eval below (positive
  reads + the negative-capability proof), captured repeatably.
- Task runner is `just`; Terraform is `terraform fmt`-clean and passes
  `terraform validate` per root (`CLAUDE.md` "Key Conventions";
  `.pre-commit-config.yaml` local `terraform-fmt` + `terraform-validate`).
- Pre-existing issues the change runs into are fixed, not skipped
  (`.claude/rules/pre-existing-issues.md`).
- Any new/changed `docs/*.md` passes the slop scan
  (`.claude/rules/slop-scan-for-docs.md`).
- Adversarial review before declaring done
  (`.claude/rules/adversarial-reviews.md`).

## Code surface (exact anchors)

- **New Terraform (infrastructure root).** Add
  `vault_consul_secret_backend_role "deploy"` + the scoped Consul ACL
  policy string. Land it in `deployments/infrastructure/secrets.tf`
  (alongside the existing `vault_mount "kvv2"` at line 2) or a sibling
  `consul_secrets.tf` in the same root, following the `secrets.tf` resource
  shape (lines 2-7). This root is the one that provisions Vault engines
  today, so the `deploy` role belongs here, not in `applications` (Q1
  covers which root; recommendation: infrastructure). The
  `vault_consul_secret_backend` mount resource itself is NOT declared in
  Terraform — Ansible owns the mount (config-split invariant).
- **New Ansible task block.** Enable `consul` engine + write
  `consul/config/access`, mirroring
  `bootstrap/playbooks/seed_vault.yml:20-28` (idempotent enable) and using
  the Consul management token derived exactly as in
  `bootstrap/roles/consul_server/tasks/main.yml:92-99`
  (`master_token` from `/opt/consul/bootstrap_token`). Wire the new
  play/role into the bootstrap sequence
  (`bootstrap/justfile:41-48`, after `seed_vault.yml` at line 44). Q1
  decides new playbook vs extending `seed_vault.yml` vs a role.
- **State backend (read-only reference; drives the policy).**
  `deployments/infrastructure/backend.tf:2`,
  `deployments/applications/backend.tf:2`,
  `deployments/infrastructure/vars/backend-config.hcl:2` (path
  `terraform/infrastructure`),
  `deployments/applications/vars/backend-config.hcl:2` (path
  `terraform/applications`). The `key_prefix "terraform/"` write grant is
  derived from these two paths.
- **Service reads (read-only reference; drives the policy).**
  `deployments/applications/services.tf:1-9` (`consul_service` minio /
  postgres-db). The `service "minio"` / `service "postgres-db"` read grants
  are derived from these.
- **Consumer of the token today (read-only reference; NOT changed in F6).**
  `deployments/applications/providers.tf:34-38` and the justfiles'
  `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` lines. F8 changes these; F6 leaves
  them.
- **Consul ACL policy DSL precedent.**
  `bootstrap/roles/consul_server/files/agent_policy.hcl` (the
  `node_prefix`/`service_prefix`/`key_prefix`-style rules the `deploy`
  policy will use, scoped down rather than the agent policy's blanket
  `write`).
- **Provider version (read-only reference).**
  `deployments/infrastructure/providers.tf:7-9` (`vault ~>5.3.0`).

## Tests & validation gates

**Repo gate:** `just pre_commit` (config `gates: ["just pre_commit"]`,
`.loop/config.json`), which runs `pre-commit run --all-files`
(root `justfile:17-18`). Hooks (`.pre-commit-config.yaml`): `check-json`,
`check-ast`, `check-merge-conflict`, `check-yaml --unsafe`,
`debug-statements`, `detect-private-key`, `end-of-file-fixer`, local
`nomad-fmt` on `*.hcl`, local `terraform-fmt` (`terraform fmt -check
-recursive`) and `terraform-validate` (`scripts/tf_validate.sh`, which runs
`terraform validate` offline per root:
`deployments/infrastructure`, `deployments/applications`,
`deployments/applications/modules/bucket`). Any `.tf` this ticket adds is
caught for both fmt and schema. `.claude/` and `.loop/` are excluded
(`.pre-commit-config.yaml:1`), so this ticket file is not linted; the new
`.tf` and any new Ansible `.yml` are. YAML task files must pass
`check-yaml`. This gate proves formatting and Terraform schema; it does NOT
exercise the live engine. The evals below do.

**Evals (live cluster).** The cluster is reachable via `VAULT_ADDR` +
`VAULT_TOKEN` and `CONSUL_HTTP_ADDR` + `CONSUL_HTTP_TOKEN`
(`.devcontainer/.env.example`). Each eval is a command plus its expected
result. Run the **pre-apply** evals before adding the role (they confirm the
engine Ansible enables is present), then the **at-close** evals after the
Terraform `deploy` role applies.

Pre-apply (after the Ansible engine-enable step has run on the cluster):

1. **Consul secrets engine is mounted.**
   `vault secrets list -format=json | jq -e '."consul/"'`
   -> exit 0, a JSON object with `"type": "consul"`. Confirms the Ansible
   `vault secrets enable -path=consul consul` step.
2. **Engine access is configured.**
   `vault read consul/config/access` (or the equivalent read)
   -> exit 0, shows the configured Consul `address` and scheme. Confirms
   `consul/config/access` was written by Ansible.

At-close (after `terraform apply` on the infrastructure root):

3. **`deploy` role exists with a bounded TTL.**
   `vault read -format=json consul/roles/deploy`
   -> exit 0; `.data` shows the attached scoped policy (by name) and a
   `max_ttl`/`ttl` in the ~30-60 min band (Q2). Confirms
   `vault_consul_secret_backend_role "deploy"`.
4. **Brokering yields a short-lived token.**
   `vault read -format=json consul/creds/deploy`
   -> exit 0; returns `.data.token` (a Consul SecretID) and a
   `lease_duration` in the ~30-60 min band, not infinite.
5. **Positive capability — state KV write.** Export the brokered token as
   `CONSUL_HTTP_TOKEN`, then write and read a scratch key under the state
   prefix: `consul kv put terraform/_f6probe ok && consul kv get
   terraform/_f6probe`
   -> exit 0, prints `ok`. Proves the token satisfies the state backend
   (the load-bearing requirement F8 depends on). Clean up
   `consul kv delete terraform/_f6probe`.
6. **Positive capability — service reads.** With the same brokered token,
   `consul catalog service minio` and
   `consul catalog service postgres-db`
   -> exit 0, each returns the service's node(s). Proves the two
   `consul_service` data reads (`applications/services.tf:1-9`) still
   resolve under the scoped token.
7. **Negative capability (required) — out-of-scope write denied.** With the
   same brokered token, attempt a KV write OUTSIDE the granted prefix and an
   ACL operation:
   `consul kv put not-terraform/_f6probe nope`
   -> Permission denied / HTTP 403; AND
   `consul acl token list`
   -> Permission denied / HTTP 403. Proves the `deploy` policy is
   least-privilege: it does NOT carry the management/global-write power the
   static bootstrap token has. This negative proof is the core of the
   ticket; a `deploy` token that can do either of these has failed F6.

Capture the eval commands and observed results in the ticket's eval marker
so acceptance stays repeatable, then delete any scratch keys.

**Required artifacts:** the Terraform `deploy` role + scoped policy (fmt-
clean, `terraform validate`-green), the Ansible engine-enable task block
(`check-yaml`-clean, idempotent), the eval transcript (positive reads + the
negative-capability proof), and a green `just pre_commit`.

**Eval marker (Definition of Done, five-column scenarios):**
`.loop/evals/F6-foundation-vault-consul-secrets-engine.md`. The consumer
sets `require_eval: true` (`.loop/config.json`), so the loop refuses pickup
until this marker exists — co-author it with the `create-eval` skill before
implementation.

## Risk assessment

- **Blast radius (low-to-medium, well contained in F6).** F6 is additive:
  a new Vault mount and a new role/policy. It does NOT touch the running
  static-token path (`providers.tf`, justfiles, `.env`), so a mistake in the
  `deploy` role cannot break current deploys — the deployer keeps using its
  static token until F8. The one shared surface is the Vault `consul/` mount:
  if Ansible and Terraform both tried to own it, they would fight. The
  config split (Ansible owns the mount + `config/access`, Terraform owns only
  the role/policy) is precisely what avoids that; getting it wrong is the
  main risk.
- **Reversibility.** Fully reversible. `vault secrets disable consul`
  removes the engine and every brokered lease; deleting the Terraform role
  resource removes the role. No existing token or workflow is mutated.
- **Likeliest failure modes.**
  (a) **State-backend lockout risk deferred to F8, but seeded here:** if the
  `deploy` policy omits or misscopes `key_prefix "terraform/"`, the brokered
  token cannot read/write state, and F8's cutover would brick every deploy.
  Eval 5 exists to catch this now.
  (b) **`consul_service` read too narrow:** if the policy grants
  `service` read but not the `node` read the catalog surface needs, eval 6
  fails; widen minimally per Q3.
  (c) **Dual-ownership of the mount:** if the Terraform side is written to
  declare `vault_consul_secret_backend` (the mount) rather than only the
  role, it collides with the Ansible-enabled mount — duplicate-mount or
  drift/destroy on apply. The config-split invariant forbids this.
  (d) **TTL too short with no renew:** a 30-min lease without auto-renew can
  expire mid-apply on a long run; Q2's renewable setting mitigates, and F8
  owns the renew wiring.
  (e) **Over-grant:** a `deploy` policy with `acl = "write"` or a blanket
  `key_prefix "" { policy = "write" }` silently reproduces god-mode. Eval 7
  is the guard.

## Subtickets (ordered, dependency-aware)

1. **Derive and freeze the minimal `deploy` Consul policy.** From the
   anchors: `key_prefix "terraform/" { policy = "write" }` (state, both
   roots) + read on services `minio` and `postgres-db` (+ minimal `node`
   read if the catalog read needs it, Q3). No management, no global write.
   Record the derivation. Blocks everything else.
2. **Ansible: enable + configure the Consul secrets engine.** New task block
   mirroring `seed_vault.yml:20-28` (idempotent enable) and deriving the
   Consul management token as in `consul_server/tasks/main.yml:92-99`. Wire
   into `bootstrap/justfile:41-48` after `seed_vault.yml`. Resolve Q1
   (playbook vs role) first. Run pre-apply evals 1-2.
3. **Terraform: `deploy` role + scoped policy** in the infrastructure root
   (`secrets.tf` or a sibling `consul_secrets.tf`), TTL per Q2, policy from
   subticket 1. `terraform fmt` + `validate` green.
4. **Run the at-close evals** (3-7) on the live cluster, capture positive
   reads AND the negative-capability proof, delete scratch keys.
5. **`just pre_commit` + adversarial review.**

## Open questions (forks the operator must settle)

- **Q1 — Where does the Ansible engine-enable live: a new playbook, an
  extension of `seed_vault.yml`, or a role?** `seed_vault.yml:20-28` already
  enables a KV engine with the Vault root token and is the natural sibling,
  but it runs on `hosts: manager` and seeds bootstrap secrets, not Consul
  wiring. **Recommendation:** add the `consul` engine enable +
  `config/access` as a new task block in `seed_vault.yml` (it already has
  the Vault root token and the manager host) OR a small dedicated playbook
  `enable_consul_secrets.yml` wired into `bootstrap/justfile` right after
  `seed_vault.yml` (line 44). Prefer the dedicated playbook if the Consul
  management-token lookup (from `/opt/consul/bootstrap_token`) makes
  `seed_vault.yml` awkward; both keep the config split intact.
- **Q2 — Exact TTL and renew semantics for the `deploy` role.** Decided
  band is ~30-60 min with auto-renew during a run. **Recommendation:**
  `ttl = "30m"`, `max_ttl = "60m"` on the role; leave the *renew* wiring
  (the terraform-run auto-renew loop) to F8, since F6 does not run the
  deployer against the brokered token. F6 only needs the role to mint a
  bounded, renewable lease; eval 4 checks the band.
- **Q3 — Does `service` read alone satisfy `consul_service`, or is a `node`
  read also required?** The `consul_service` data source returns
  `node_address` (`applications/providers.tf:41,47`), which may require a
  `node`/`node_prefix` read grant in addition to `service` read.
  **Recommendation:** start with `service "minio" { policy = "read" }` +
  `service "postgres-db" { policy = "read" }`; if eval 6 fails on node
  resolution, add the minimal `node_prefix "" { policy = "read" }` (read,
  never write). Confirm empirically at apply rather than over-granting up
  front.
- **Q4 — The `CONSUL_TOKEN` vs `CONSUL_HTTP_TOKEN` `.env.example` skew.**
  The real `.devcontainer/.env` uses `CONSUL_TOKEN` (line 5) and the
  justfiles map `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}`, but
  `.devcontainer/.env.example:6` documents the source var as
  `CONSUL_HTTP_TOKEN`. **Recommendation:** leave it for F8 (the cutover that
  actually changes how the deployer sources its Consul token); fixing it in
  F6 is out of scope and risks confusing the cutover diff. Flag it so F8
  reconciles the example with the brokered-token flow.
- **Q5 — Which Terraform root owns the `deploy` role?** The role is a Vault
  object; both roots configure `provider "vault" {}`. The infrastructure
  root already owns all Vault-engine provisioning
  (`secrets.tf`, the KV mount). **Recommendation:** infrastructure root, so
  Vault-side provisioning stays in one place and the role exists before the
  applications root ever needs a Consul token. The Ansible engine-enable
  must run before this root's apply (bootstrap ordering already guarantees
  Ansible precedes Terraform).
- **Q6 — Does the deployer's real Consul footprint include anything the
  grep missed (e.g. locks/sessions the Consul state backend takes)?** The
  Consul state backend acquires a session/lock on the KV path for state
  locking. `key_prefix "terraform/" { policy = "write" }` covers the KV;
  Consul session creation may need a `session_prefix` grant.
  **Recommendation:** include
  `session_prefix "terraform/" { policy = "write" }` in the `deploy` policy
  defensively (state locking is load-bearing for the backend), and let eval
  5 confirm a full put/get/lock cycle works. This is the one place a
  slightly broader-but-still-scoped grant is justified; document why.
