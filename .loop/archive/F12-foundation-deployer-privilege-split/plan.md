---
epic = "foundation"
depends_on = []
priority = 45
summary = "Give the applications Terraform root its own Vault identity holding three grants. Measured: it plans clean, covers every write that root performs, and is denied all four escalation routes. This is the root that changes weekly, and it needs almost nothing. The infrastructure root is F13."
tags = ["vault", "terraform", "deployer"]
---

# F12 — A least-privilege deployer for the applications root

## Title
Give `deployments/applications/` a Vault identity holding three grants, so the
Terraform root that changes every week stops running on the root token and
cannot escalate if it leaks.

## Size / Effort
**S.** One Vault policy, one identity. The policy is already measured against
both a real plan and real writes; the work is turning a probe into a resource
and proving it again under review.

## Triggered by
The operator wants the root token out of daily use. This was half of F7, which
was retired on 2026-08-01 after failing plan review twice. F7 derived one
policy from the union of both Terraform roots and got a near-root policy it
then described as least privilege.

**Splitting by root is what made the problem tractable**, and it came from one
measurement nobody had taken.

## The measurement

Inventoried every `vault_*` resource in both roots on 2026-08-01:

| Root | Vault resources | Privileged? |
| --- | --- | --- |
| `deployments/applications/` | 13 `vault_kv_secret_v2`, 3 `ephemeral` reads | **No.** Zero `sys/*`, `auth/*` or `identity/*` |
| `deployments/infrastructure/` | 9 KV secrets **plus** an auth backend, a mount, 2 policies, 9 identity/OIDC resources, a JWT role, 2 engine roles | **Yes** |

The applications root is the one that changes weekly, and it touches nothing
but KV. That is this ticket. The infrastructure root is **F13**, which is a
harder problem and should not hold this one up.

## Context (today's state)

**Measured against the live cluster on 2026-08-01. Where a claim is reasoned
rather than measured, it says so.**

### Three grants are enough. Measured.

A Vault token holding exactly this ran `terraform plan` in
`deployments/applications/` to completion — full refresh of all 16 Vault
resources plus Nomad, MinIO, Postgres and Bifrost — ending in `No changes.`

```hcl
path "auth/token/create" { capabilities = ["create","update"] }

# one pair per sub-prefix this root actually touches:
# postgres, phoenix, memex, loki, mlflow, hermes, bifrost, minio
path "secret/data/default/<prefix>/*"     { capabilities = ["create","read","update","delete"] }
path "secret/metadata/default/<prefix>/*" { capabilities = ["read"] }
```

**The prefix is enumerated, not `default/*`, and that closes a real
escalation.** `default/vault/operator` holds the human operator's userpass
password (`deployments/infrastructure/secrets.tf:121-135`), so a blanket
`secret/data/default/*` read lets this deployer read it and log in as the
operator — worth nothing today, because that entity carries no policy, and
worth `human-read` the moment F11 lands. Enumerating the eight sub-prefixes
this root writes renames nothing and also drops the Grafana admin password,
the ACME TransIP credentials, the HAProxy TLS key and the GCS backup keys out
of reach. Measured 2026-08-01: the enumerated policy reaches `No changes`, can
read, write and delete under its own prefixes, and is **denied**
`default/vault/operator`, `default/grafana/admin` and `default/acme`.

**The metadata grant is read-only, and the data grant drops `patch`.** An
earlier draft gave metadata full CRUD, justified by the 10 resources that set
`custom_metadata` — all of which are in the **infrastructure** root
(`secrets.tf` 6, `backup.tf` 4). This root has no `backup.tf` and sets no
`custom_metadata`, `max_versions`, `cas_required` or `delete_all_versions`.
Metadata `read` is still required, and for a non-obvious reason: a KV v2 data
read returns `"custom_metadata": null` as a *present* key, so the provider
calls `readKVV2Metadata` on every refresh regardless. Metadata `list` and
`delete` have no caller, and destroy issues `DELETE secret/data/<name>` rather
than touching metadata, because `delete_all_versions` defaults to false — the
repo states this at `deployments/infrastructure/acme.tf:38-40`. `patch` is
dead because create and update both go through `util.RetryWrite`, a POST.
All measured: the plan reaches `No changes` with metadata at `read` only.

### `auth/token/create` is not optional, and no code review would find it.

Vault provider 5.3.0 mints a child token at configure time, before it reads
any resource. The live `default` policy does **not** grant that path — read
directly on 2026-08-01. Measured: a KV-only token gets `permission denied` on
`vault token create` and the plan dies at provider configure; adding the one
grant makes both succeed. It appears in no `vault_*` resource block.
**This is the mechanical bug that killed F7's policy.**

### The identity cannot escalate. Measured.

With that token, all four denied:

| Attempt | Result |
| --- | --- |
| `vault policy write` (rewrite its own policy) | denied |
| `vault auth enable -path=probe-esc userpass` | denied |
| `vault write identity/entity name=… policies=root` | denied |
| `vault token create -policy=root` | denied |

It holds no `sys/*`, no `identity/*`, and no `auth/*` beyond token creation,
so there is no path from it to more privilege. That is what makes this a real
boundary rather than a smaller pile of privilege.

### The rest of the ground

- **`bootstrap/` is a separate KV mount, not a subtree.** Every key under
  `secret/` begins `default/`, so `secret/data/default/*` genuinely excludes
  the founding credentials. Verified by denial from a scoped token.
- **Writes work.** With the earlier full-CRUD probe token: `kv put`,
  `kv metadata put -custom-metadata=…` and `kv metadata delete` all succeeded.
  The first and last are what this root needs.
- **Terraform authenticates by env var.** Both roots declare a bare
  `provider "vault" {}` (`deployments/applications/providers.tf:36`), reading
  `VAULT_ADDR` and `VAULT_TOKEN` from the shell, filled from
  `.devcontainer/.env` by `.devcontainer/devcontainer.json:37-40`. The root
  token sits there today.
- **State lives in Consul** and needs a token with `key_prefix "terraform/"`
  write, which `consul/creds/deploy` supplies. Confirmed: the measured plan
  ran with a brokered Consul token. Separate concern from the Vault token, and
  unchanged by this ticket.
- **The policies that exist today** are `acme-tls-write`, `default`,
  `default-ceiling`, `nomad-workloads` and `root` (`vault policy list`,
  2026-08-01). None is root-equivalent apart from `root`.

## Non-goals / out of scope
- **The infrastructure root. That is F13**, and it is a genuinely harder
  problem: that root manages ACL policies and identity objects, and a token
  that can do both can escalate to root in two steps. Do not try to solve it
  here, and do not create a policy for it here.
- **No provider block changes and no `.devcontainer/.env` edit.** Wiring the
  provider to this identity is F8. This ticket creates the identity and proves
  the root runs under it, driven by hand.
- **No revocation of the root token.** The infrastructure root still needs a
  privileged one until F13 and F8 land.
- **No human identity.** F11 owns `human-read`. This ticket must not add
  policy to the `operator` entity or to F11's `humans` group.
- **No change to what the applications root manages.** No resource moves, and
  no `vault_*` resource is added or removed.
- No change to `nomad_deploy_role.tf`, `consul_deploy_role.tf`, or the
  `deploy` ACL policies on either side.

## Requirements & restrictions
1. **A Vault policy named `deployer-applications`** with exactly the three
   path blocks measured above. Not a superset "to be safe": every grant traces
   to a measured 403 without it, and Requirement 6 re-proves that.
2. **The metadata grant is `read, list, delete`.** No `create`, no `update`.
   If a future applications resource sets `custom_metadata`, `max_versions`,
   `cas_required` or `delete_all_versions`, this grant must widen and the
   ticket that adds it owns that change.
3. **The policy is created by Terraform in the infrastructure root**, as a
   `vault_policy` resource in the shape of `vault_policy.acme_tls_write`
   (`acme.tf:41`). The infrastructure root is the more privileged of the two,
   so it owning the less privileged one is the right direction. Do not apply
   it by hand with `vault policy write`; that creates drift the next apply
   reverts.
4. **A dedicated identity, separate from the human and separate from the
   infrastructure deployer.** Q1 settles the mechanism. It is never attached
   to the `operator` entity or to F11's `humans` group, because that would
   hand a human the deployer's write capability and undo F11's central claim.
5. **Prove it by running the root, not by reading the policy.** The root must
   reach `terraform plan` clean **and** `terraform apply` clean under this
   identity with `VAULT_TOKEN` carrying no other grant. A policy that has
   never run an apply is a guess; plan never exercises a write.
6. **Prove minimality.** Remove each of the three grants in turn and show the
   plan fails. A policy that still passes with a grant removed is carrying
   privilege this ticket did not justify.
7. **Prove the denials, not only the grants.** The four escalation probes are
   deliverables. They are the only evidence the split achieved anything.
8. **Docs**: name the identity, what the applications root needs, and why it
   differs from the infrastructure root. State that F13 owns the other half
   and that the root token is still required until it lands.
9. Plain language in every doc, comment and commit message
   (`.claude/rules/plain-language.md`).
10. Adversarial review by a sub-agent before this is reported done
    (`.claude/rules/adversarial-reviews.md`).

## Code surface
- `deployments/infrastructure/deployer_applications.tf` **(new)**:
  `vault_policy.deployer_applications`, plus the identity — a `userpass` user
  via `vault_generic_endpoint`, an entity and an alias, mirroring
  `auth_userpass.tf:28-56`. Unlike the `operator` entity, this one carries
  `deployer-applications` (see Q2 for why directly and not through a group).
- `docs/vault-human-auth.md` **(edit)** or a new sibling doc.

**Do not touch**: `providers.tf` in either root, `.devcontainer/.env`,
`auth_userpass.tf`, `nomad_deploy_role.tf`, `consul_deploy_role.tf`, or
anything F11 creates.

## Tests & validation gates
- **Gate**: `just pre_commit` from the repo root (`.loop/config.json:2-4`).
- `terraform validate` and `terraform plan` in both roots — the policy is
  declared in the infrastructure root, so that root must also still plan.
- The proof runs are the eval marker at
  `.loop/evals/F12-foundation-deployer-privilege-split.md`.

## Risk assessment
- **Blast radius: small.** Everything is additive. Nothing consumes the
  identity until F8, and the root token keeps working throughout.
- **Reversibility: high.** Delete the policy and the identity. Both roots go
  on as before.
- **The failure mode with real cost is a policy too narrow, discovered
  mid-apply**, leaving the root half-applied. Requirement 5 demands an apply
  for exactly this, and the mitigation is to keep the root token available in
  a second shell while running it.
- **The failure mode with lasting cost is scope creep back toward F7.** If
  implementing this starts to need `sys/*` or `identity/*`, something has
  moved into the wrong root and the answer is to stop, not to widen. Say so
  and re-scope.
- No secret is rotated. No cluster service restarts.

## Open questions

**Q1. How does the deployer authenticate: userpass, AppRole, or a long-lived
token?**
*Settled: `userpass`, one user for this deployer.* AppRole is the textbook
answer for machine identity and is the better long-term shape. It is not
chosen here because `userpass` is already live (F2), already has a Terraform
pattern to copy (`auth_userpass.tf:28-56`), and its credential drops into
`.devcontainer/.env` exactly where the root token sits, which makes F8's
cutover a swap rather than a redesign. **The earlier draft argued AppRole
would create a bootstrap problem this repo does not otherwise have. That was
false** — `vault_auth_backend.userpass` (`auth_userpass.tf:13-17`) is owned by
the same infrastructure root that would need `sys/auth/approle`, so the repo
has exactly that shape already. The conclusion stands on the other reasons.
Revisit when a second machine runs Terraform.

**Q2. Bind the policy to the entity directly, or through a group?**
*Settled: directly on the entity.* F11 uses a group because its membership is
expected to grow — more humans. A deployer identity is one machine role and a
group of one is structure without a reason. It also keeps the two bindings
visibly different, so nobody adds a human to a deployer group by reflex.

**Q3. Should this identity also broker Nomad and Consul tokens?**
*Settled: no.* The applications root does need a Consul token for its state
backend, but that is F8's wiring question, and the measured plan ran with a
brokered Consul token supplied separately. Granting `consul/creds/deploy` here
would be speculative, and `nomad/creds/deploy` doubly so.

**Q4. Both roots write `secret/data/default/*`. Should the prefix be split by
root?**
*Settled: no.* It is possible and not worth the churn: it would rename live
secret paths, which every Nomad job template reads. The overlap is real and
accepted.

## Definition of Done
`deployments/applications/` plans and applies clean under a Vault token whose
only grants are `auth/token/create`, `secret/data/default/*` and
`secret/metadata/default/*` at read/list/delete. Removing any one of the three
breaks the plan. All four escalation probes are denied. The root token is not
used at any point in the proof, and the docs say plainly that it is still
required for the infrastructure root until F13 lands.
