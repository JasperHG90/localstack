---
verdict: fail
---

# Plan review — F7-foundation-deployer-vault-oidc-login (pass `plan-validator`, RE-REVIEW)

Plan reviewed: `/home/vscode/workspace/.loop/plans/F7-foundation-deployer-vault-oidc-login.md`
sha256 verified locally: `75c6bdac5010e5aa85caff60d9b3e90c9749dd78f34485d8487f105833a57841`
(matches the briefing fingerprint; withheld from the header because this is a
`fail` and must not authorize the flip to `ready`).

Eval marker reviewed: `/home/vscode/workspace/.loop/evals/F7-foundation-deployer-vault-oidc-login.md`
(rewritten 2026-07-31, 14 rows).

## Premise verdict: PARTIALLY SOUND — gate verdict `fail`

The replan is a real improvement and gets the two hardest calls right. The
`sudo` measurement is correct, the Nomad-ACL-policy-in-Ansible reasoning is
correct, the `default/*` prefix is a genuine boundary, and the rewritten eval
rows can actually fail. But the replan's headline claim — "Fix 1 — the policy,
derived from the resource graph" — is still incomplete in exactly the way the
last verdict named. A policy built to the Fix-1 table **cannot `terraform plan`
either root**, because it walked `vault_*` *resources* and missed what the Vault
*provider itself* calls before it reads a single resource. It also cannot
`terraform apply` the infrastructure root, for a second reason no row in the new
eval can catch. And the grant set it mandates is root-equivalent by a one-step
self-rewrite, which inverts the ticket's stated contract while eval row 11
claims to guard it.

## Load-bearing assumptions

### P1 — The Fix-1 table is the set of Vault paths a `deployer` token needs to `terraform plan` both roots. BREAKS

**Missing `auth/token/create`.** Both roots declare a bare `provider "vault" {}`
(`deployments/infrastructure/providers.tf:28`,
`deployments/applications/providers.tf:36`). The pinned provider is 5.3.0
(`deployments/infrastructure/.terraform.lock.hcl:87-89`). In that provider,
`internal/provider/meta.go:337-346` reads
`skipChildToken := GetResourceDataBool(d, consts.FieldSkipChildToken,
consts.EnvVarSkipChildToken, false)` and, when false, calls `createChildToken`;
`meta.go:608-613` is `clone.Auth().Token().Create(...)`, i.e. `POST
auth/token/create`. The default is `false`, and nothing in this repo or the
harness env sets it (`grep -rn 'skip_child_token\|TERRAFORM_VAULT_SKIP_CHILD_TOKEN'`
over `*.tf`, `*.sh`, `*.yml`, `justfile` returns nothing; `env | grep
TERRAFORM_VAULT` is empty).

`auth/token/create` is **not** in the built-in `default` policy on this cluster.
Live `vault policy read default` grants only `auth/token/lookup-self`,
`auth/token/renew-self`, `auth/token/revoke-self`, `sys/capabilities-self`,
`identity/entity/{id,name}/…`, `sys/internal/ui/resultant-acl`, `sys/renew`,
`sys/leases/*`, `cubbyhole/*`, `sys/wrapping/*`, `sys/tools/hash*`,
`sys/control-group/request`, `identity/oidc/provider/+/authorize`.

So a `deployer` token built to the Fix-1 table fails at **provider configure**,
before any resource is refreshed. This is the same failure class the previous
verdict called most dangerous ("a policy that cannot plan its own root"), just
one level up the stack. Eval rows 1 and 2 would surface it at implementation
time, but the plan is the spec and its spec is wrong.

**Missing `create`/`update` on `secret/metadata/default/*`.** The table grants
that path `read, list, delete` only. But `vault_kv_secret_v2` writes the
metadata endpoint whenever `custom_metadata` is set: provider
`vault/resource_kv_secret_v2.go:250-257` — `metadataPath := getKVV2Path(mount,
name, consts.FieldMetadata)` then `client.Logical().Write(metadataPath, cm)`.
This repo sets `custom_metadata` in **10 places**
(`deployments/infrastructure/secrets.tf:23,60,82,111,…` and
`deployments/infrastructure/backup.tf`; `grep -rn custom_metadata deployments
--include=*.tf | wc -l` = 10). This is an **apply-time-only** failure, so eval
rows 1 and 2 (`terraform plan`) cannot catch it and no other row probes a
metadata write. The plan's own §9 names this exact shape — "KV2 v2 path split
forgotten (`data/` granted, `metadata/` not, or vice-versa)" — and then commits
it in the Fix-1 table.

**`sys/mounts/secret` is an exact-match grant, and the provider also hits
`sys/mounts/secret/tune`.** Vault ACL paths are exact unless they end in `*` or
contain `+`, so `path "sys/mounts/secret"` does not cover
`sys/mounts/secret/tune`. The provider binary carries the literal
`/v1/sys/mounts/%s/tune`
(`strings` over
`deployments/infrastructure/.terraform/providers/registry.terraform.io/hashicorp/vault/5.3.0/linux_arm64/terraform-provider-vault_v5.3.0_x5`),
used by `updateMount` (`vault/resource_mount.go:284-320`). Update-time only, so
lower severity than the two above, but it belongs in the table.

### P2 — Only `sys/auth/*` needs `sudo` on this Vault 2.0.3; `sys/mounts/*` does not. HOLDS

Re-measured without mutating the cluster. The running server is `Vault v2.0.3`
(`vault status` → `Version 2.0.3`, build 2026-06-17, Consul storage), which is
the OpenBao 2.0.3 line. OpenBao v2.0.3 `vault/logical_system.go:81-100` declares
the `sys` backend's root-protected paths as exactly:

```
"auth/*", "remount", "audit", "audit/*", "raw", "raw/*", "rotate",
"config/cors", "config/auditing/*", "config/ui/headers/*",
"plugins/catalog/*", "revoke-prefix/*", "revoke-force/*",
"leases/revoke-prefix/*", "leases/revoke-force/*", "leases/lookup/*",
"leases", "internal/inspect/*"
```

`mounts/*` is absent; `auth/*` is present. That corroborates the plan's live
probe: enabling a secrets mount needs an ordinary grant, enabling an auth method
needs `sudo`. One caveat I can flag but not close: this build reports itself as
"Vault" and carries a non-upstream `agent_registry` secrets engine (`vault
secrets list`), so it is a fork, and a fork could in principle have edited that
list. The plan's own no-sudo probe measured the running binary directly, which is
the stronger evidence, and my source check agrees with it. HOLDS.

The `sudo` capability itself is not the escalation risk here; see P4.

### P3 — Granting the prefix `secret/data/default/*` is a real boundary, not a widening. HOLDS

Every KV2 path this repo touches is under `default/`. Verified by enumerating
each `name` on every `vault_kv_secret_v2` resource, `data` source and `ephemeral`
block in both roots: `deployments/infrastructure/secrets.tf:17,39,54,76,101,106,123,142`,
`deployments/infrastructure/backup.tf:36,52,67,83`,
`deployments/infrastructure/acme.tf:102`,
`deployments/applications/secrets.tf:4,13,24,33,44,55,64,81,96,107,119,130,140`,
`deployments/applications/services.tf:13,18,214`. All 26 begin `default/`.
`secret_mount = "secret"` in both `vars/prod.tfvars.example:1`. The `bootstrap/`
KV data the plan says stays out is a **separate mount** (`vault secrets list`
shows `bootstrap/` as its own kv engine), so the prefix genuinely excludes it.
The prefix is the honest shape and the enumeration was the wrong shape.

Two count errors, immaterial to the decision but they show the walk was not
re-run: the infrastructure root has **11** `vault_kv_secret_v2` resources
(7 in `secrets.tf`, 4 in `backup.tf`), not 9, so "22 enumerated names" is 24.

### P4 — The Fix-1 grant set is not root-equivalent. BREAKS

The table grants `sys/policies/acl/deployer` `create, read, update, delete` —
"this ticket's own policy". Vault applies no special protection to a token
rewriting the policy it is bound to. A `deployer` token can therefore issue one
`vault policy write deployer` with `path "*" { capabilities = ["create","read",
"update","delete","list","sudo"] }` and hold full Vault privilege on its next
request. That is root-equivalence in a single call, reached through a grant the
plan mandates and the eval **requires**: marker row 5 ("Positive control in the
same family") scores the `sys/policies/acl/deployer` write as a must-succeed.

Meanwhile marker row 11 is "Guardrail: the policy is not root-equivalent",
scored by an adversarial reviewer against the rendered HCL. A document with no
`path "*"` passes row 11 while row 5 has just certified the write that produces
one. That is structurally the same defect the previous verdict called fatal: a
guardrail that certifies the escalation green.

This may be unavoidable if Terraform is to manage its own deployer policy — but
the plan never names the tension, and this ticket's premise is "least privilege
is the deliverable" (§6: "Least privilege is the explicit contract of this
ticket"). The fork (author `deployer` in Ansible alongside the other bootstrap
policies, vs. accept self-rewrite and say so) is exactly the kind of decision
that belongs in Open Questions with a recommendation.

Secondary over-grants in the same table, lower confidence and lower severity:
`identity/*` CRUD+list is broader than the nine resources need and covers
`identity/entity` / `identity/group` policy assignment; `auth/jwt-nomad/role/*`
and `auth/userpass/users/*` let the deployer mint auth roles with arbitrary
`token_policies`. Whether Vault refuses `root` in those fields I did not settle,
so I mark those **UNCERTAIN** rather than guess. `sys/policies/acl/deployer`
needs no such qualifier.

### P5 — The login half is dead: F2 shipped `userpass`, so no OIDC login method is needed. HOLDS

`.loop/ledger.json` has `F2-foundation-vault-oidc-provider` at stage `done`.
Live `vault auth list` returns `jwt-nomad/`, `token/`, `userpass/`. The
`userpass` backend is in this Terraform root at
`deployments/infrastructure/auth_userpass.tf:13`, with the generic-endpoint user
at `:28`, the entity at `:38` and the alias at `:48`. Live `vault read
identity/entity/name/operator` returns id `351f302a-ada1-0e79-15d3-e22a4be2e3e4`,
`policies: []`, one group id — exactly what marker row 10 asserts. The front door
exists and F7 does not build one. `depends_on = F2` is now correct and Q1 is
genuinely closed.

### P6 — The Nomad read ACL policy must live in Ansible, because a brokered `nomad/creds/*` token is `type: client` and cannot write Nomad ACL policies. HOLDS

Three independent checks:

- **Nomad requires a management token for ACL policy writes.** HashiCorp's API
  docs for `/v1/acl/policy` list `ACL Required: management` on *Create or Update
  Policy*, *Delete Policy* and *List Policies* (fetched from
  `https://developer.hashicorp.com/nomad/api-docs/acl/policies`). Nomad ACL
  policy HCL has no `acl` block, so no client policy can grant it.
- **The brokered role is `type: client`.**
  `deployments/infrastructure/nomad_deploy_role.tf:36-41` sets `type = "client"`.
- **The Ansible precedent is exactly where the plan says.**
  `bootstrap/roles/nomad_server/tasks/main.yml:182-187` is "Create Nomad developer
  policy", running `nomad acl policy apply … developer
  /opt/nomad/policies/nomad_developer_policy.hcl` with `NOMAD_TOKEN:
  "{{ nomad_bootstrap_token }}"` — the management token. Live `nomad acl token
  self` on the harness token reports `Type = management`, confirming that is what
  applies policies today.

The "do not reuse `developer`" claim also holds:
`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl` grants
`alloc-exec` and `alloc-node-exec` plus `host_volume "*" { policy = "write" }`,
`node`, `agent` and `operator` read.

The cross-reference is real too:
`.loop/plans/F8-foundation-deployer-provider-cutover.md:514-550` carries the
matching decision to move `nomad_acl_policy.deploy` to Ansible. Note "can never
be applied by the deployer it defines" is true **after** F8's cutover; today
`provider "nomad" {}` reads the management `NOMAD_TOKEN` from env and
`nomad_acl_policy.deploy` sits in Terraform at
`deployments/infrastructure/nomad_deploy_role.tf:14`. The plan does not state
that ordering, which matters for P8.

### P7 — F5, F6 and F8 state as restated in Fix 4. HOLDS

`.loop/ledger.json`: F5 `done`, F6 `done`, F8 `blocked`
(`unresolved-design-fork`, its own premise). `nomad/` and `consul/` engines are
live (`vault secrets list`), and the role resources are shipped at
`deployments/infrastructure/nomad_deploy_role.tf:36` and
`consul_deploy_role.tf:19`. Eval row 7 is exercisable now, as claimed.

### P8 — The rewritten eval rows can actually fail. MOSTLY HOLDS; three rows are defective

The marker is a real improvement: rows 1, 2, 4 (second half), 5, 6, 7, 8 and 10
are falsifiable, and rows 1 and 2 are exactly the check the previous verdict
demanded. Three problems:

- **Row 3 contradicts the plan's own Fix-1 table.** Its input is `vault auth
  enable -path=probe-f7 userpass` under a `deployer` token, expecting the mount
  to be created. That writes `sys/auth/probe-f7`. The Fix-1 table grants
  `sys/auth/userpass` — an **exact path**, not a prefix. Row 3 is unpassable
  against the policy the plan specifies, and the only way to pass it is to widen
  to `sys/auth/*`, which is more privilege than the resource graph needs. The
  replan's prose is inconsistent on the same point: it says "**Only `sys/auth/*`
  needs `sudo`**" over a table row scoped to `userpass`. Row 3 also enables a real
  auth method on the live cluster and relies on manual cleanup.
- **Row 9's scorer produces a false red.** Its input is `grep -rn
  'nomad_acl_policy' deployments/**/*.tf`. That matches the pre-existing
  `nomad_acl_policy "deploy"` at
  `deployments/infrastructure/nomad_deploy_role.tf:14`, which F7 does not touch
  (F8 moves it). Scope the row to the new read policy by name. Separately,
  `deployments/**/*.tf` does not recurse in bash without `globstar`.
- **Row 4's first half is a tautology.** `vault token create -policy=root` is
  refused for any non-root token lacking `sudo` on `auth/token/create`, whatever
  the rest of the policy says, so it passes even against a wildly over-broad
  `deployer`. The marker itself says the second half is "the discriminating one",
  which is right; the first half adds noise.

Row 2 carries an honest-bound problem the plan does not state: `terraform plan`
on `deployments/applications` configures the `minio`, `postgresql`, `consul` and
`bifrost` providers (`deployments/applications/providers.tf:38-73`), so it needs
the whole stack up and non-Vault credentials in env. It can go red for reasons
unrelated to the `deployer` policy. That is the safe direction, but it should be
written down.

### P9 — The superseded body no longer contradicts the replan. BREAKS

The replan opens with a blanket "supersedes every conflicting statement above",
and it is far more disciplined than a bare stub: it answers each of the seven
fixes by number and states a new one-line deliverable. But four conflicts survive
in load-bearing places:

- **Frontmatter `summary` (`:5`)** still reads "Replace the Terraform deployer's
  static Vault root token with an operator OIDC login, and author a scoped
  deployer policy granting exactly the KV2, nomad/creds, consul/creds, and
  database/creds paths it needs." This is machine-read metadata, not prose a
  supersede clause reaches. It names a deliverable the replan deleted (OIDC
  login) and a path set the replan dropped (`database/creds`). §1 Title
  (`:13-18`) has the same problem, and Fix 5 explicitly says to strike it.
- **§6 requirement 2 (`:164-167`)** still states "The policy MUST NOT be
  root-equivalent: no `path "*"`, no `sys/*` management capability, no `auth/*`
  or `identity/*` write." That is the exact inversion of Fix 1's table, sitting
  in the section headed "Must achieve" — the one an implementer reads as
  normative.
- **§8 evals 1-4 (`:256-276`)** still encode the old scoring, including the false
  guardrail at `:266-271` that the marker rewrite exists to delete.
- **§11 Q3 and Q5 (`:374-395`)** remain open. The replan's heading is "**Open
  questions, all closed**" but it closes only Q1, Q2 and Q4. Q3
  (`database/creds/*` breadth) is silently dropped — the Fix-1 table has no
  `database/` row, which is probably right since `vault secrets list` has no
  `database/` mount, but "all closed" over-claims while §6 still demands the
  grant.

### P10 — The code surface covers the work the replan added. BREAKS

§7 (`:194-225`) was never updated. It has no home for:

- the **Ansible half** of NEW SCOPE (a new
  `bootstrap/roles/nomad_server/files/*.hcl` and a task in
  `bootstrap/roles/nomad_server/tasks/main.yml` beside `:182-187`), which marker
  rows 8 and 9 score;
- the **policy-to-entity binding** (marker row 10 requires a login to carry
  `deployer`; `auth_userpass.tf:28-36` writes `token_policies = []` and the
  entity's live `policies` is `[]`, so something must bind — a
  `vault_identity_group` with `policies = ["deployer"]`, or an edit to that
  generic endpoint). Neither is named anywhere;
- the **runbook** the replan closed Q4 on ("Yes, add one").

§7 also still instructs the implementer to add the `vault_jwt_auth_backend` /
`vault_jwt_auth_backend_role` OIDC wiring the replan deleted, and to write
`vars/prod.tfvars`, which Fix 7 correctly says is git-ignored (`.gitignore:12`,
`**/vars/prod.tfvars`). The create-ticket contract's "tests homed in the code
surface" is not met for rows 8, 9 and 10.

### P11 — The repaired anchors resolve. HOLDS

`deployments/infrastructure/acme.tf:41` = `resource "vault_policy" "acme_tls_write"`;
`:66` = `resource "vault_jwt_auth_backend_role" "acme"`;
`deployments/applications/providers.tf:36` = `provider "vault" {}`;
`justfile:17-19` = the `pre_commit` recipe running `pre-commit run --all-files`;
`.gitignore:12` = `**/vars/prod.tfvars`;
`deployments/infrastructure/auth_userpass.tf:13` = `resource "vault_auth_backend" "userpass"`;
`deployments/infrastructure/secrets.tf:2` = `resource "vault_mount" "kvv2"`;
`bootstrap/roles/nomad_server/tasks/main.yml:182-184` = the developer-policy task.
All six repairs from fix 6 land.

### P12 — The gate is discovered, not assumed. HOLDS

`.loop/config.json` `gates` = `["just pre_commit"]`, `require_eval: true`.
`.pre-commit-config.yaml:22-24` (`terraform-fmt`) and `:28-30`
(`terraform-validate`, `entry: scripts/tf_validate.sh`). Unchanged from the last
review.

## Most dangerous assumption

**P1** — that walking the `vault_*` resources yields the complete path set. It
does not, because the provider's own bootstrap call (`auth/token/create`) is not
a resource, and one resource's metadata write (`secret/metadata/default/*`
create/update, 10 occurrences) is invisible at plan time. A policy built to the
Fix-1 table dies at provider configure on the very first `terraform plan`, which
is the same defect that blocked this ticket the first time. P4 runs it close: the
plan mandates the one grant that makes the policy root-equivalent, and the eval
row that claims to guard root-equivalence cannot see it.

## Required fixes before this plan can leave PLANNING

1. **Add `auth/token/create` (`update`) to the Fix-1 table**, or set
   `skip_child_token = true` on both `provider "vault"` blocks and say so. The
   5.3.0 provider mints a child token on every configure
   (`internal/provider/meta.go:337-346`, `:608-613`); the `default` policy does
   not grant it. Without this the policy cannot plan either root.
2. **Change `secret/metadata/default/*` to `create, read, update, delete, list`.**
   `custom_metadata` appears 10 times in
   `deployments/infrastructure/{secrets,backup}.tf`, and
   `vault/resource_kv_secret_v2.go:250-257` writes the metadata endpoint for each.
   Add an eval row that exercises a metadata write, since rows 1 and 2 are
   plan-only and cannot see an apply-time denial.
3. **Widen `sys/mounts/secret` to cover `sys/mounts/secret/tune`** (Vault ACL
   paths are exact without a trailing `*`), or state that mount tuning is out of
   scope and the deployer will fail on a `vault_mount` config change.
4. **Name the self-rewrite and decide it.** `sys/policies/acl/deployer` write
   makes the token root-equivalent in one call, and marker row 5 requires that
   write while row 11 claims to forbid root-equivalence. Either move the
   `deployer` policy to Ansible with the other bootstrap policies, or accept the
   self-rewrite explicitly in the plan and rewrite row 11 so it is not scoring a
   property the design deliberately gives up. This cannot stay unstated in a
   ticket whose §6 says least privilege is the contract.
5. **Reconcile eval row 3 with the Fix-1 table.** Row 3's `vault auth enable
   -path=probe-f7` writes `sys/auth/probe-f7`, which the table's exact-path
   `sys/auth/userpass` denies. Pick one: grant `sys/auth/*` (and say why the
   widening is acceptable) or change the row to probe `sys/auth/userpass`. Fix
   the same inconsistency in the Fix-1 prose.
6. **Scope eval row 9 to the new read policy.** `grep -rn 'nomad_acl_policy'
   deployments/**/*.tf` matches the pre-existing
   `deployments/infrastructure/nomad_deploy_role.tf:14`, which F8 owns, so the
   row goes red on correct F7 work. Also drop the `**` glob, which does not
   recurse without `globstar`.
7. **Update §7's code surface** to cover what the replan added: the Ansible task
   and policy file beside `bootstrap/roles/nomad_server/tasks/main.yml:182-187`,
   the `vault_nomad_secret_role` for the read role, the policy-to-entity binding
   marker row 10 requires (the entity's live `policies` is `[]` and
   `auth_userpass.tf:28-36` writes `token_policies = []`), and the runbook Q4
   closed on. Delete the `vault_jwt_auth_backend` wiring and the
   `vars/prod.tfvars` write, both of which the replan reverses.
8. **Edit the superseded body rather than relying on the blanket clause.** At
   minimum: the frontmatter `summary` (`:5`) and §1 title (`:13-18`), which still
   sell an OIDC login and `database/creds`; §6 requirement 2 (`:164-167`), which
   states the exact opposite of the Fix-1 table inside "Must achieve"; and §8
   evals 1-4 (`:256-276`), which still carry the false guardrail. Frontmatter is
   machine-read and no prose clause supersedes it.
9. **Close or re-open Q3 and Q5 honestly.** The heading says "Open questions, all
   closed" but §11 Q3 (`database/creds/*` breadth) and Q5 (where the policy is
   managed) are untouched, and the Fix-1 table silently drops `database/`
   altogether. State that `database/` has no mount yet and the grant is deferred
   to S2/R3, or grant it.
10. **Record row 2's honest bound.** `terraform plan` on
    `deployments/applications` configures the minio, postgresql, consul and
    bifrost providers (`deployments/applications/providers.tf:38-73`), so it
    needs the full stack up and non-Vault credentials. Say what a red there does
    and does not prove.

## Contract hygiene (secondary)

- **Resolved anchors:** the six repairs from the last verdict all land (P11).
  Two new counts are wrong (11 infra KV resources, not 9), immaterial to the
  decision.
- **Discovered gates:** holds (P12).
- **Explicit non-goals:** present. §5's F5/F6 language is stale; the closing
  "What this ticket still does NOT do" is correct and useful.
- **Tests homed in the code surface:** fails for marker rows 8, 9 and 10 (P10).
- **Forks surfaced:** the three the replan closes are closed with evidence. Two
  forks are now buried rather than surfaced: the self-rewrite (P4) and Q3/Q5 (P9).

## Ticket state

The `unresolved-design-fork` blocker no longer fits: Q1 is genuinely settled
(userpass, shipped by F2, verified live), so the design fork that blocked this
ticket is resolved. But the plan is not ready. It must stay at `PLANNING` and
must not flip to `ready`; if the blocker code is re-labelled, the right reason is
a failing plan review, not an open fork.
