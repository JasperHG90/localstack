---
verdict: fail
---

# Plan review — F8-foundation-deployer-provider-cutover (pass `plan-validator`)

Fingerprint verified locally:
`sha256sum .loop/plans/F8-foundation-deployer-provider-cutover.md` →
`b27b95da74d5a33e79b8a74a21cea205d95ed3d0fd2b47f3d2fa8e58455ce929` (matches
the briefing). The `plan:` line is omitted because this is a `fail`.

## Premise verdict: BROKEN

The plan was authored 2026-07-24. Since then T1/T2/T3 (2026-07-26) and B1
(2026-07-29/30) landed and changed both the file surface and the resource
inventory this cutover must apply. Separately, and more seriously, F8's
acceptance criteria require a full `terraform apply` of the infrastructure
root under credentials that its declared dependencies F5 and F7 do not and
cannot issue. Two of the eleven assumptions below sink the ticket's own
Definition of Done. `fail`.

## Load-bearing assumptions

### P1 — The F7 `deployer` Vault policy is a sufficient credential to run `terraform apply` on the infrastructure root. **BREAKS** (most dangerous)

The plan's Live-reconcile step 1 and eval row 3 require `just apply` on
`deployments/infrastructure` "using only the brokered path", where the
`vault` provider carries the operator's F7 OIDC token
(`.loop/plans/F8-...md:110-114, 168-170, 326-328`).

The infrastructure root manages these Vault objects:

| Resource | Anchor | Vault path it writes |
|---|---|---|
| `vault_mount.kvv2` | `deployments/infrastructure/secrets.tf:2` | `sys/mounts/<mount>` |
| `vault_policy.acme_tls_write` | `deployments/infrastructure/acme.tf:41` | `sys/policies/acl/acme-tls-write` |
| `vault_jwt_auth_backend_role.acme` | `deployments/infrastructure/acme.tf:66` | `auth/jwt-nomad/role/acme` |
| `vault_nomad_secret_role.deploy` | `deployments/infrastructure/nomad_deploy_role.tf:36` | `nomad/role/deploy` |
| `vault_consul_secret_backend_role.deploy` | `deployments/infrastructure/consul_deploy_role.tf:19` | `consul/roles/deploy` |

F7's plan grants the `deployer` policy exactly: KV2 `data`/`metadata` under
`default/`, plus **read** on `nomad/creds/deploy`, `consul/creds/deploy`,
`database/creds/*` — and states as a hard requirement "The policy MUST NOT be
root-equivalent: no `path "*"`, no `sys/*` management capability, no `auth/*`
or `identity/*` write"
(`.loop/plans/F7-foundation-deployer-vault-oidc-login.md`, §6 Requirement 2).
F7 eval 3 makes `vault write sys/policies/acl/xyz` returning 403 "the
definitive least-privilege check".

So the credential F7 is designed to produce is, by construction, denied every
one of the five writes above. `nomad/role/*` and `consul/roles/*` are not even
covered by read (F7 grants `nomad/creds/deploy`, not `nomad/role/deploy`).
F8 asserts F7's output is sufficient and never reconciles the two.

Live confirmation that neither side exists yet, so nothing has silently
resolved this: `vault auth list` returns only `jwt-nomad/` and `token/` (no
`oidc`, no `approle`), and `vault policy list` returns
`acme-tls-write, default, nomad-workloads, root` — no `deployer`.

### P2 — The brokered `nomad/creds/deploy` token can run a full `terraform apply` of the infrastructure root. **BREAKS**

Requirement 8 (`:218-235`) demands "a real `terraform apply` … of the
infrastructure root under the minted `deploy` token". That root contains
`resource "nomad_acl_policy" "deploy"`
(`deployments/infrastructure/nomad_deploy_role.tf:13`). Creating or updating a
Nomad ACL policy requires a **management** token; the live Vault role is
`type: "client"` with `policies: ["deploy"]` (`vault read nomad/role/deploy`),
and the live `deploy` Nomad policy grants only `namespace "default"`
capabilities — `submit-job`, `read-job`, `host-volume-create/register/read/
write/delete` — with no `acl` or `operator` block (`nomad acl policy info
deploy`, and the source at `nomad_deploy_role.tf:17-29`).

The brokered token therefore cannot manage the ACL policy that defines it.
This is a circular dependency in the ticket's own acceptance gate, and the
plan does not mention it. (A no-op *refresh* may succeed, since Nomad lets a
token read a policy attached to it, so I mark the read path UNCERTAIN — but
the "full apply" the requirement demands is a management operation.)

### P3 — `deployments/applications/providers.tf` anchors. **BREAKS**

Every cited line in this file is off by four, and a provider the plan does not
know about now exists. B1 (`ac3267b`, 2026-07-29; `e17d8d0`, 2026-07-30) added
`bifrost` to `required_providers` and a `provider "bifrost"` block.

| Plan claim | Actual |
|---|---|
| `required_providers` `:1-27` | `:1-32` |
| `provider "nomad" {}` `:30` | `:34` |
| `provider "vault" {}` `:32` | `:36` |
| `provider "consul"` `:34-38` | `:38-42` |
| "inline comment at line 35" | `:39` |
| minio/postgresql `:40-53` | `:44-57` |

Consequences beyond the numbers: the plan says "two of the five providers"
already broker from Vault (`:71-72`); there are now seven providers and
**three** broker from Vault (`provider "bifrost"` at `:59-69` consumes
`ephemeral.vault_kv_secret_v2.bifrost_admin`). §Code surface's instruction "Do
not touch the `minio`/`postgresql`/`vault` blocks (lines 32, 40-53)"
(`:258-259`) both misnames the lines and omits `bifrost` entirely.

`deployments/applications/services.tf:11-19` (the ephemeral blocks) and all
`deployments/infrastructure/providers.tf` anchors (`:19-22`, `:26`, `:28`,
`:30-32`) DO resolve exactly as described.

### P4 — "three `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` prefixes" in the applications justfile at lines 10, 14, 18. **BREAKS**

`git show 5778a85:deployments/applications/justfile` confirms exactly three, at
10/14/18, as of 2026-04-29 — true at authoring. Commit `e17d8d0` (2026-07-30)
rewrote `apply` into a two-branch recipe and added `state_rm`. There are now
**five** occurrences, at lines **10, 18, 22, 27, 31**
(`deployments/applications/justfile`); line 14 is now `#!/usr/bin/env bash`.

An implementer following Requirement 5 (`:197-204`) and §Code surface
(`:274-277`) literally would replace three and leave `${CONSUL_TOKEN}` bound in
the targeted-apply branch and in `state_rm` — which is precisely failure mode
5 the plan itself names (`:378-381`). `deployments/infrastructure/justfile:8,
12,16` still resolves correctly.

### P5 — F8 can "hand a lease-TTL requirement back to F5/F6". **BREAKS**

Requirement 4 (`:190-196`) and Q3 (`:471-475`) both defer the lease-sizing fix
to F5/F6. Both tickets are `done` and archived
(`.loop/ledger.json`; `.loop/archive/F5-…/`, `.loop/archive/F6-…/`). There is
no F5/F6 left to receive a requirement — F8 owns it or nobody does.

The live values are already fixed and are hard ceilings:
`vault read nomad/config/lease` → `ttl 30m, max_ttl 1h`;
`vault read consul/roles/deploy` → `ttl 1800, max_ttl 3600`. The code that sets
them is `bootstrap/roles/nomad_server/tasks/main.yml:309` and
`deployments/infrastructure/consul_deploy_role.tf:23-24`. **Neither file is in
F8's §Code surface.** A default 30-minute lease against a full `applications`
apply is exactly the mid-apply-expiry failure the plan flags at `:363,372-374`,
and with F5/F6 closed there is no other owner.

### P6 — Requirement 9's target file is in the code surface. **BREAKS (contract)**

Requirement 9 (`:236-252`) instructs F8 to change `session_prefix "terraform/"`
to `session_prefix ""`. I verified the anchor: the grant is at
`bootstrap/playbooks/enable_consul_secrets.yml:46-48`, and the paired-with-
`node_prefix` precedent it cites exists in
`bootstrap/roles/consul_server/files/agent_policy.hcl`. The *claim* holds. But
§Code surface (`:254-289`) lists only six files, none under `bootstrap/`. A
mandatory requirement with no code-surface home violates the create-ticket
contract's "real code surface" clause. Same gap for Requirement 8's optional
policy trim, which would touch `deployments/infrastructure/nomad_deploy_role.tf`.

### P7 — The eval encodes the Definition of Done. **BREAKS (shape-check)**

`.loop/evals/F8-foundation-deployer-provider-cutover.md` has seven rows. Two
are grep/shape scorers that pass against wrong content:

- **"Guardrail: no static privileged token remains in the repo"** —
  `git grep -nE 'NOMAD_TOKEN|CONSUL_HTTP_TOKEN|CONSUL_TOKEN|VAULT_TOKEN'`
  with expected "Only intended references (address/comment lines)". A grep that
  always returns hits, judged by prose, is not deterministic. Given P4, this
  row would pass a human skim while two live `${CONSUL_TOKEN}` bindings remain.
- **"Guardrail: Vault is the only directly-authenticated provider"** — "Grep
  both `providers.tf` files" for `token` fields "sourced from Vault reads".
  This passes against `token = data.vault_generic_secret.x.data["token"]`
  pointing at the *wrong path*, or an empty string interpolation.

Missing rows: nothing encodes Requirement 8 (the host-volume apply proof) or
Requirement 9 (the real state-locking cycle), so the two relayed findings are
unenforced by the DoD.

### P8 — Terraform is v1.12.2. **BREAKS (low severity)**

`terraform version` → **v1.14.3** on linux_arm64. Cited twice (`:47-49`,
`:125`). The conclusion drawn (ephemeral resources available) still holds, so
this is a factual staleness, not a design break.

### P9 — Ephemeral variants may exist for the Nomad/Consul creds reads (Q3). **BREAKS as an open question — it is settleable offline and the answer is no**

I dumped the pinned provider's schema from the installed binary
(`/home/vscode/workspace/deployments/infrastructure/.terraform/providers/registry.terraform.io/hashicorp/vault/5.3.0`,
via a filesystem mirror in a scratch dir, `-backend=false`):

- `ephemeral_resource_schemas` = **exactly** `["vault_database_secret",
  "vault_kv_secret_v2"]`.
- `vault_nomad_access_token` exists **only** as a data source (attributes:
  `accessor_id, backend, id, namespace, role, secret_id`).
- `vault_generic_secret` exists as a resource and a data source, not as an
  ephemeral.
- No `vault_consul_access_token` in any schema section.

So the plan's P-claims at `:36-44` and `:123-128` HOLD, and Q2's shape
recommendation is right. But Q3's "prefer ephemeral reads if the provider
exposes them" branch is dead: **both brokered tokens will be written to
Terraform state, unconditionally.** That state lives in Consul KV over plain
HTTP (`scheme = "http"`, `deployments/{applications,infrastructure}/vars/backend-config.hcl:3`).
The plan waves this through as "state is in the private Consul backend"
(`:469-471`) without noting the transport.

### P10 — "As of writing, no `F5`/`F6`/`F7` plan files exist in `.loop/plans/`." **BREAKS (stale)**

`.loop/plans/F7-foundation-deployer-vault-oidc-login.md` exists; F5 and F6 are
`done` with plans archived under `.loop/archive/`. The §Dependencies paragraph
(`:423-425`) contradicts the plan's own Requirements 8 and 9, which relay
findings *from completed* F5/F6 runs.

### P11 — "the 8 `nomad_dynamic_host_volume` resources". **BREAKS (minor)**

Nine now. T3 (`a6cc9c6`, 2026-07-26) added
`nomad_dynamic_host_volume.acme_lego_state`
(`deployments/infrastructure/acme.tf:14`). Live:
`nomad volume status -type host` lists 9 ready volumes including
`acme_lego_state`.

### Assumptions that HOLD (checked, no instance found)

- **The Consul state backend is credentialed at init by env, before the
  provider graph.** `deployments/{applications,infrastructure}/backend.tf:1-3`
  are bare `backend "consul" {}`; the backend-config files set `address`,
  `path`, `scheme` and **no token**. Q1's framing is correct.
- **The state paths sit under the prefix F6's policy grants.**
  `path = "terraform/applications"` and `"terraform/infrastructure"` vs
  `key_prefix "terraform/" { policy = "write" }`
  (`bootstrap/playbooks/enable_consul_secrets.yml:43-45`). Q1's "confirm the F6
  role scopes state-path access" resolves YES.
- **The Consul `deploy` policy covers every consul-provider read the
  applications root makes.** Exactly two `data "consul_service"` (minio,
  postgres-db) at `deployments/applications/services.tf:1-9`, matched by the
  `service "minio"` / `service "postgres-db"` / `node_prefix ""` grants.
- **`.devcontainer/.env.example:2,6,10`** — `NOMAD_TOKEN`,
  `CONSUL_HTTP_TOKEN`, `VAULT_TOKEN` resolve exactly. File untouched since
  2026-04-24.
- **The offline gate never touches the backend.** `scripts/tf_validate.sh` uses
  `init -backend=false` and skips init entirely when `.terraform` exists. The
  plan's "necessary, not sufficient" reading is right.
- **Live engines exist as F5/F6 delivered them.** `vault secrets list` shows
  `nomad/` (type nomad) and `consul/` (type consul); `vault list nomad/role`
  and `vault list consul/roles` each return `deploy`;
  `vault read nomad/config/access` → `http://127.0.0.1:4646`;
  `vault read consul/config/access` → `127.0.0.1:8500`, `http`. No creds
  endpoint was read.
- **Gate discovery.** `.loop/config.json` `gates` = `["just pre_commit"]`;
  root `justfile:18-19` runs `pre-commit run --all-files`; the
  `terraform-fmt` / `terraform-validate` local hooks and the
  `exclude: '^\.(claude|loop)/'` all match the plan. (Cited as `justfile:17-18`;
  actual `18-19` — trivial.)
- **Non-goals are explicit** (`:137-158`) and forks live in Open Questions with
  recommendations (`:444-485`). Those two contract clauses are met.

## Most dangerous assumption

**P1.** If F7's `deployer` policy is what F7's plan says it is — no `sys/*`,
no `auth/*`, read-only on the two creds paths — then F8's central acceptance
criterion, a clean `just apply` of the infrastructure root under the brokered
path, cannot pass, and F8's whole framing ("the F7 OIDC session is the only
credential entry point") is unachievable without either widening F7's policy
toward the root-equivalence it exists to prevent, or splitting the
privileged-Vault-object subset of the infra root out of the deployer's reach.
That fork is not in the plan at all, in any section. Everything else here is
repairable by editing anchors; P1 is a design question F8 must answer before
it can be picked up.

## Required fixes before this plan can leave PLANNING

1. **Reconcile P1 with F7.** Add an Open Question (or a §Requirements clause)
   naming the five infra-root Vault objects that the F7 `deployer` policy
   forbids, and settle the fork: widen F7's policy, split the root, or accept
   that the infra root keeps a separate privileged Vault path. Do not leave
   "apply the infra root under the F7 session" as an untested assertion.
2. **Reconcile P2.** State how `nomad_acl_policy.deploy`
   (`deployments/infrastructure/nomad_deploy_role.tf:13`) is applied, given the
   brokered token is `type: client` and Nomad ACL writes need management.
   Requirement 8's "full apply" proof is unrunnable until this is answered.
3. **Re-anchor `deployments/applications/providers.tf`** to `:34`, `:36`,
   `:38-42`, `:44-57`, `:1-32`, and account for `provider "bifrost"`
   (`:59-69`) in the "do not touch" list and in the provider count at `:71-72`.
4. **Re-anchor `deployments/applications/justfile`** to five occurrences at
   lines 10, 18, 22, 27, 31 (not three at 10, 14, 18) in both Requirement 5 and
   §Code surface.
5. **Take ownership of the lease TTL.** F5/F6 are closed. Add
   `bootstrap/roles/nomad_server/tasks/main.yml:309` (`ttl=30m max_ttl=1h`) and
   `deployments/infrastructure/consul_deploy_role.tf:23-24` (`ttl=1800`,
   `max_ttl=3600`) to §Code surface, and replace "hand the number to F5/F6"
   with a decision F8 makes.
6. **Add `bootstrap/playbooks/enable_consul_secrets.yml` to §Code surface** as
   the home of Requirement 9's `session_prefix ""` change (anchor `:46-48`),
   and `deployments/infrastructure/nomad_deploy_role.tf` for Requirement 8's
   optional policy trim.
7. **Close Q3's ephemeral branch.** vault 5.3.0 exposes ephemerals only for
   `vault_database_secret` and `vault_kv_secret_v2`; both brokered tokens WILL
   land in state, and that state travels to Consul over plain HTTP. State this
   as settled, not open.
8. **Harden the eval.** Replace the two grep guardrails with checks that fail
   on wrong content (e.g. assert `git grep -c '\${CONSUL_TOKEN}' -- deployments`
   returns 0, and assert the resolved provider token path is
   `nomad/creds/deploy` / `consul/creds/deploy`), and add rows for
   Requirement 8's host-volume apply and Requirement 9's state-locking cycle.
9. **Correct the stale facts.** Terraform is v1.14.3 (not v1.12.2); nine
   dynamic host volumes (not eight, `acme.tf:14` added the ninth); F7's plan
   exists and F5/F6 are done — rewrite the §Dependencies paragraph at `:423-425`.
