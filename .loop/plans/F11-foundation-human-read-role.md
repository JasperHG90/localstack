---
epic = "foundation"
depends_on = ["F2-foundation-vault-oidc-provider"]
priority = 46
summary = "One Vault identity group, `developer`, carrying one policy that covers everything a human does on this cluster: both Terraform roots, brokered Nomad and Consul tokens, user and group management, and every secret under default/. Bound to the operator entity. This is the ticket that retires the root token."
tags = ["vault", "human-auth", "terraform", "rbac"]
---

# F11 — The `developer` group

## Title
Create one Vault policy and one identity group that let a human log in with
`userpass` and do everything they do today with the root token, so the root
token stops being a daily credential.

## Size / Effort
**S.** One `vault_policy`, one `vault_identity_group`, one membership. Every
capability and denial below was run on 2026-08-01 — the plan path against the
live cluster, the apply path against a throwaway `vault server -dev` with the
repo's pinned provider.

## Triggered by
The operator, after a day of this being over-designed:

> *"Make me a policy that allows `localstack login` for a human developer, and
> for that developer to then deploy the Terraform."*

Earlier attempts (F7, then a three-way F11/F12/F13 split) separated human from
deployer and chased a privilege boundary between them. The operator collapsed
the two on 2026-08-01: **one group, `developer`, covers both.** F12 and F13
were dropped in that call.

## The policy, measured

**A Vault token is not sufficient on its own.** Both roots keep state in Consul
(`infrastructure/backend.tf:2`, `applications/backend.tf:2`), so every run below
also needs a Consul token with `key_prefix "terraform/"` write and
`session_prefix "terraform/"` write — brokered separately with
`vault read consul/creds/deploy` and passed as `CONSUL_HTTP_TOKEN`. This policy
grants the read that brokers it; it does not replace it. Every measurement below
was taken that way.

Every line below was proven on 2026-08-01. A token holding exactly this policy
and nothing else, with a brokered Consul token alongside it:

| Probe | Result |
| --- | --- |
| `terraform plan` in `deployments/infrastructure/` | `No changes` |
| `terraform plan` in `deployments/applications/` | `No changes` |
| `vault read nomad/creds/deploy` | works |
| `vault read consul/creds/deploy` | works |
| `vault write identity/group name=… policies=…` | works |
| `vault write auth/userpass/users/…` | works |
| `vault kv get -mount=secret default/grafana/admin` | works |
| `vault kv list -mount=bootstrap /` | **denied** |
| `vault read sys/audit` | **denied** |
| `vault operator key-status` | **denied** |
| `vault write sys/mounts/secret/tune description=…` | works (needs its own grant) |
| `vault write sys/auth/userpass/tune description=…` | works (needs its own grant **with `sudo`**) |
| `terraform apply` changing an auth mount description | needs `sys/mounts/auth/userpass/tune` — a **different** endpoint from the CLI one, and denied there it **fails silently** |

```hcl
# The provider mints a child token LAZILY, on first use, and CACHES it per
# ProviderMeta -- `setClient` opens with `if p.client != nil { return nil }`
# (`internal/provider/meta.go:184-188`). A successful run mints ONCE, not
# once per resource.
#
# But a FAILED mint never populates `p.client`, so every resource retries and
# fails again. A missing grant therefore surfaces as one error per resource,
# each carrying a resource address, all after `Refreshing state...` -- not as
# a single failure before the graph is read. The live `default` policy does
# NOT grant this path, and it appears in no vault_* resource block, which is
# why two earlier attempts missed it.
path "auth/token/create" { capabilities = ["create", "update"] }

# Mounts and auth methods the infrastructure root manages.
path "sys/mounts"         { capabilities = ["read", "list"] }
path "sys/mounts/secret"  { capabilities = ["create", "read", "update", "delete"] }
path "sys/auth"           { capabilities = ["read", "list"] }
path "sys/auth/userpass"  { capabilities = ["create", "read", "update", "delete", "sudo"] }
# The provider issues GET sys/mounts/auth/<path> to read mount tuning.
# Also in no resource block.
path "sys/mounts/auth/*"  { capabilities = ["read"] }
# Mount paths are EXACT MATCH, so the two above do not cover `.../tune`.
# Both `vault_mount.kvv2` and `vault_auth_backend.userpass` carry a
# `description`, and changing one is an in-place tune. The SECRET mount's
# tune 403s honestly at apply. The AUTH mount's does not -- see the
# silent-failure section below.
path "sys/mounts/secret/tune" { capabilities = ["create", "read", "update"] }
# TWO auth-tune endpoints exist and they are not interchangeable. The
# PROVIDER writes `sys/mounts/auth/<path>/tune`; the `vault auth tune` CLI
# writes `sys/auth/<path>/tune`. Grant both: the first is what Terraform
# needs, the second is what a human needs, and granting only the CLI path
# is the defect this plan shipped once already.
#
# `sudo` on the `sys/auth/` form is required and the mount grant does not
# confer it, because `sys/auth/*` is root-protected. Measured denied without
# it. The `sys/mounts/auth/` form needs no `sudo`.
path "sys/mounts/auth/userpass/tune" { capabilities = ["create", "read", "update"] }
path "sys/auth/userpass/tune"        { capabilities = ["create", "read", "update", "sudo"] }

# Policy and identity management: creating users, groups and their grants.
path "sys/policies/acl"   { capabilities = ["list"] }
path "sys/policies/acl/*" { capabilities = ["create", "read", "update", "delete"] }
path "identity/*"         { capabilities = ["create", "read", "update", "delete", "list"] }
path "auth/userpass/users/*" { capabilities = ["create", "read", "update", "delete", "list"] }
path "auth/jwt-nomad/role/*" { capabilities = ["create", "read", "update", "delete"] }

# Secrets-engine roles the infrastructure root manages.
path "nomad/role/*"   { capabilities = ["create", "read", "update", "delete"] }
path "consul/roles/*" { capabilities = ["create", "read", "update", "delete"] }

# The KV domain this repo owns. `bootstrap/` is a separate mount, not a
# subtree, so THIS POLICY does not name it. That is not a boundary: the
# holder can grant themselves the mount in three commands. See the plan.
path "secret/data/default/*"     { capabilities = ["create", "read", "update", "delete", "patch"] }
path "secret/metadata/default/*" { capabilities = ["create", "read", "update", "delete", "list"] }
path "secret/metadata/default"   { capabilities = ["list"] }

# Brokered tokens: `localstack login`, and F8's provider cutover.
path "nomad/creds/deploy"  { capabilities = ["read"] }
path "consul/creds/deploy" { capabilities = ["read"] }
```

### The one failure mode here that produces no error

Denied on `sys/mounts/auth/<path>/tune`, the Vault provider does not raise.
The cause is a shadowed variable at `vault/resource_auth_backend.go:222-225`
in provider 5.3.0: the tune error is discarded and a nil one returned in its
place. It is specific to `vault_auth_backend`; all 17 resource types these two
roots use were scanned and this is the only one.
Measured on a throwaway server with an audit device enabled: `terraform apply`
exits 0, prints `2 changed`, leaves the live value untouched, and **writes the
unapplied value into state**. There is no 403 in the output and no audit device
on this cluster to see the denial. So a policy missing that one grant looks
like a clean apply and silently desynchronises state from reality. Any check
that scores "no 403 appeared" cannot catch it; the eval compares live against
state instead.

The `default` policy already covers token self-service (`lookup-self`,
`renew-self`, `revoke-self`, `sys/capabilities-self`,
`sys/internal/ui/resultant-acl`), read live 2026-08-01, so none of it is
restated here.

## This is not a containment boundary, and that is deliberate

A `developer` can write `identity/*` and `sys/policies/acl/*`, so they can
grant themselves anything short of `root`. Vault refuses to attach the `root`
policy — measured — and refuses nothing else.

That is the operator's call, made on 2026-08-01 when collapsing Developer and
Deployer into one group. **No doc, comment or commit message in this ticket
may describe this policy as least privilege.** What it buys over the root
token is precisely this and no more: a per-person credential that can be
revoked by removing it from the group.

**Everything else is reachable, in three commands.** A `developer` writes a
policy, attaches it to their own group, and logs in again — measured, and the
mechanism is the one two paragraphs above. That includes `sys/audit` and the
`bootstrap` mount. So this plan claims **no** access boundary. The denial rows
in the eval record what the *policy as written* refuses, which is a different
and weaker statement, and the docs must not upgrade it.

**Two things it does not buy, despite being obvious to claim.** There is no
audit attribution, because **no audit device is enabled on this cluster** —
`vault audit list` returns "No audit devices are enabled", measured
2026-08-01. Enabling one is its own ticket and the docs must not imply
otherwise. And `sys/unseal` is an unauthenticated path: a `developer` token
reaches it and fails on the key argument, not on permission. `vault operator
key-status` is the real denial to check.

## Non-goals
- **The rest of the role taxonomy.** `F14` owns `admin` and the extendible
  application-user scaffold.
- **The `admin` group and the application-user scaffold.** Those are `F14`.
  `D5` owns the breakglass *procedure* that uses `admin`.
- **Service accounts.** `F1` (Nomad workload identity), `M1` (MinIO), `R3`
  (Postgres) already own those.
- **The Ansible half of deploying.** SSH keys and the bootstrap tokens are not
  Vault-brokered, so this group covers Terraform and not `just bootstrap`.
- **No provider change and no `.devcontainer/.env` edit.** Pointing Terraform
  at this identity is `F8`. This ticket proves both roots run under it by hand.
- **No revocation of the root token.** It stops being needed. Removing it is
  `F8`'s cutover.
- **No Nomad or Consul ACL policy changes.** The brokered `deploy` roles
  already exist and this group reads them as they are.

## Requirements
1. **A `vault_policy` named `developer`** with exactly the paths above.
2. **A `vault_identity_group` named `developer`**, type `internal`, carrying
   that policy, with `vault_identity_entity.operator.id` as a member. Bind
   through the group, not by setting `token_policies` on the auth mount and
   not on the entity, so adding a person is one membership entry. The group
   name also rides the OIDC `groups` claim (`oidc.tf:39`), which is how F14
   and the per-app tickets consume it.
3. **Both created by Terraform in the infrastructure root**, in the shape of
   `vault_policy.acme_tls_write` (`acme.tf:41`) and
   `vault_identity_group.smoke` (`oidc.tf:92`). Never applied by hand — with
   one necessary exception: **restoring `auth/token/create` after the
   minimality probe removes it.** Measured: with that grant gone, every apply
   dies at the first resource for want of it, so Terraform cannot restore its
   own policy. Only a hand `vault policy write` recovers, and the probe must
   name that recovery step before it runs.
4. **Prove it by running, not by reading.** Log in as `operator`, then from
   that session alone: plan **and apply** both Terraform roots, broker both
   tokens, create and delete a throwaway user and group, read a secret.
   **The apply must include an auth-mount description change**, and must be
   checked by comparing live against state rather than by looking for a 403 —
   see the silent-failure section. Any probe that writes to the live cluster
   restores the original value afterwards; two mount descriptions were left
   drifted this way on 2026-08-01.
5. **Prove the denials.** The `bootstrap` mount, `sys/audit` and
   `vault operator key-status` must all refuse. **Not `sys/unseal`** — it is
   unauthenticated, so any token reaches it. **Not `sys/raw`** either: this
   cluster sets no `raw_storage_endpoint`, so that path 404s even for `root`
   and a denial there proves nothing.
6. **Docs**: `docs/vault-human-auth.md` states what `developer` grants, that
   it is not a containment boundary and why that was chosen, that **no audit
   device is enabled so there is no attribution yet**, and that `F14` owns the
   taxonomy and the application-user tiers.
7. Plain language everywhere (`.claude/rules/plain-language.md`).
8. Adversarial review by a sub-agent before this is reported done
   (`.claude/rules/adversarial-reviews.md`).

## Code surface
- `deployments/infrastructure/developer_group.tf` **(new)**:
  `vault_policy.developer`, `vault_identity_group.developer`.
- `docs/vault-human-auth.md` **(edit)**.

**Do not touch**: `auth_userpass.tf`, `nomad_deploy_role.tf`,
`consul_deploy_role.tf`, `oidc.tf`, `providers.tf` in either root,
`.devcontainer/.env`.

## Tests & validation gates
- **Gate**: `just pre_commit` from the repo root (`.loop/config.json:2-4`).
- `terraform validate` and `terraform plan` in the infrastructure root.
- The proof runs are `.loop/evals/F11-foundation-human-read-role.md`.

## Risk assessment
- **Blast radius: small.** Both resources are additive. Nothing consumes them
  until `F8`, and the root token keeps working throughout.
- **Reversibility: high.** Delete the policy and the group.
- **The failure with real cost is a policy too narrow, found mid-apply**,
  leaving a root half-applied. Requirement 4 demands an apply for this reason;
  keep the root token in a second shell while running it.
- **A service does restart.** Nomad's default `change_mode` is `restart`, so
  the eval's applications-root row — which edits a `vault_kv_secret_v2` — will
  bounce the job templating that secret. Pick a secret whose consumer can take
  a restart, and expect one.

## Open questions

**Q1. Why `userpass` and not OIDC for the CLI login?**
*Settled by F2.* `userpass` shipped on 2026-07-31 and the operator entity
exists. Vault's own OIDC provider serves the web UIs and other services; the
CLI authenticates against `userpass` and brokers from there.

**Q2. Group or entity binding?**
*Settled: group.* An entity binding would have to be repeated per person, and
the group name is what the OIDC `groups` claim carries to Nomad, Grafana and
MinIO. That claim is the whole reason F14 works.

## Definition of Done
`vault login -method=userpass username=operator`, and from that session alone:
both Terraform roots plan and apply clean **including a mount-description
change**, both brokered tokens are readable, a user and a group can be created
and removed, and every secret under `default/` is readable. From the same
session the `bootstrap` mount, `sys/audit` and `vault operator key-status` all
refuse. **The `developer` session is never the root token** — checked by
asserting `identity_policies` rather than `policies`, since group binding puts
it in the former. The root token appears in the proof only as the negative
control that shows the denial rows can fire, never as the credential under
test.
