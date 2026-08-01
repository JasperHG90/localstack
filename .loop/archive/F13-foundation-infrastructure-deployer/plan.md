---
epic = "foundation"
depends_on = ["F11-foundation-human-read-role", "F12-foundation-deployer-privilege-split"]
priority = 43
summary = "Get the infrastructure Terraform root off the root token. Its 19-path policy is measured and plans clean, but a token holding both ACL-policy write and identity-group write escalates to root in two steps, so this ticket also moves every vault_policy resource out of Terraform into Ansible. That move is the deliverable, not a detail."
tags = ["vault", "terraform", "deployer", "ansible"]
---

# F13 — A scoped deployer for the infrastructure root

## Title
Give `deployments/infrastructure/` an identity that is not the root token and
cannot escalate back to it, which means moving ACL-policy authorship out of
the root that the identity deploys.

## Size / Effort
**M/L.** The policy itself is measured and small. The work is the move: three
`vault_policy` resources leave Terraform for Ansible, and one of them
(`acme-tls-write`) is live and load-bearing today. Sequencing that without a
window where the ACME renewal loses its policy is most of the ticket.

## Triggered by
F7 was retired on 2026-08-01 after failing plan review twice on the same
fault: a policy presented as least privilege that was root-equivalent by
self-rewrite. Its applications half became F12 and is clean. This is the half
that was actually hard.

## The problem, stated precisely

**A Vault token that can write any ACL policy and can write identity groups is
root, in two steps.** Vault resolves group policies at request time, so:

1. Rewrite a policy the token may write — say `acme-tls-write` — to
   `path "*"`.
2. Create an identity group carrying that policy with the token's own entity
   as a member.

The next request carries it. No new auth mount, no new user, no re-login.

The infrastructure root needs both capabilities for ordinary work. It manages
`vault_policy.acme_tls_write` (`acme.tf:41`), `vault_identity_group.smoke`
(`oidc.tf:92`), and the entity and alias at `auth_userpass.tf:38,48`. F11 adds
`vault_identity_group.humans`, and F12 adds `vault_policy.deployer_applications`.

**Narrowing the policy paths does not fix this.** An earlier draft narrowed
`sys/policies/acl/*` to exact policy names, which does close the *direct*
self-rewrite — measured: with the glob the token rewrote its own policy and
attached it to an entity, and with exact names excluding its own, the same
write was denied. But the two-step chain only needs *some* writable policy
name plus group write, and the exact-name list still has three entries.

**So the fix is to leave the token no writable policy at all.**

## Context (today's state)

**Measured against the live cluster on 2026-08-01 unless stated otherwise.**

### The 19-path policy plans clean. Measured.

```hcl
path "auth/token/create"                      { capabilities = ["create","update"] }
path "sys/mounts"                             { capabilities = ["read","list"] }
path "sys/mounts/secret"                      { capabilities = ["create","read","update","delete"] }
path "sys/mounts/auth/*"                      { capabilities = ["read"] }
path "sys/auth"                               { capabilities = ["read","list"] }
path "sys/auth/userpass"                      { capabilities = ["create","read","update","delete","sudo"] }
path "auth/jwt-nomad/role/*"                  { capabilities = ["create","read","update","delete"] }
path "auth/userpass/users/*"                  { capabilities = ["create","read","update","delete","list"] }
path "identity/*"                             { capabilities = ["create","read","update","delete","list"] }
path "nomad/role/*"                           { capabilities = ["create","read","update","delete"] }
path "consul/roles/*"                         { capabilities = ["create","read","update","delete"] }
path "secret/data/default/*"                  { capabilities = ["create","read","update","delete","patch"] }
path "secret/metadata/default/*"              { capabilities = ["create","read","update","delete","list"] }
```

That is the policy **after** this ticket's move: no `sys/policies/acl/*` at
all. The measured version that reached `No changes` also carried
`sys/policies/acl` list plus three exact policy names, because
`vault_policy.acme_tls_write` was still Terraform's. Removing those four lines
is what the move buys, and **the plan must be re-run after the move to confirm
the remainder is still sufficient** — that is Requirement 6, not an assumption
this plan makes.

Two paths a resource-graph walk cannot find, both measured:

- **`auth/token/create`.** Provider 5.3.0 mints a child token at configure
  time before reading anything, and the live `default` policy does not grant
  it. This killed F7's policy.
- **`sys/mounts/auth/*` read.** The provider issues
  `GET sys/mounts/auth/userpass` for mount tuning. Adding that one line turned
  a 403 into a clean plan. It appears in no resource block.

Unlike F12's, this policy's **apply** path is unmeasured. Metadata writes are
granted here because the 10 `custom_metadata` settings all live in this root
(`secrets.tf` 6, `backup.tf` 4), but nothing has exercised them under the
scoped token.

### What remains after the move, and it is not nothing

With no writable policy, the token can still create an identity and attach any
policy that **already exists**. Measured: it created an entity and a group
carrying `acme-tls-write`. Denied: attaching `root`, and (with exact names)
rewriting its own policy.

So the ceiling is **the union of every ACL policy on the cluster**. Today
`vault policy list` returns `acme-tls-write`, `default`, `default-ceiling`,
`nomad-workloads` and `root`. Excluding `root`, none is root-equivalent, so
today the ceiling is low. **It rises whenever anyone adds a privileged
policy** — including, after this ticket, anyone editing the Ansible playbook
that now owns them. That is a real residual and the docs must name it.

Closing it entirely means taking `identity/entity` and `identity/group` out of
Terraform too, which would mean giving up `vault_identity_group.smoke`,
`vault_identity_group.humans` and the operator entity as Terraform resources.
Not in scope. Named as the next ticket if the residual ever matters.

### Ownership and the Ansible home

- **A precedent exists and it is close.** `bootstrap/playbooks/seed_vault.yml:11-28`
  and `enable_consul_secrets.yml:15-22` are the shape to copy. The privileged
  credential is the Vault bootstrap token, which is `root_token` from
  `/opt/vault/init.json` — read at `nomad_server/tasks/main.yml:190-195`.
- **`bootstrap/justfile:40-49` names every playbook explicitly.** A new
  playbook not added there never runs, which is a silent no-op rather than an
  error.
- **Consul ACL policies are already Ansible-owned**
  (`enable_consul_secrets.yml:58`, `master_consul_token`), and the invariant
  is recorded at `consul_deploy_role.tf:5-14`. **Nomad ACL policies are
  Terraform-owned** (`nomad_deploy_role.tf:13`, management `NOMAD_TOKEN` from
  `.devcontainer/.env:2`) — do not assume symmetry, F11's first review failed
  on exactly that.
- **`acme-tls-write` is live and load-bearing.** Moving it is the risky part
  of this ticket, not the bookkeeping part.

## Non-goals / out of scope
- **The applications root. That is F12**, which is independent, measured, and
  should ship first and separately.
- **No provider block changes and no `.devcontainer/.env` edit.** That is F8.
- **No removal of `identity/entity` or `identity/group` from Terraform.** That
  would close the residual ceiling and it is a larger ticket. Name it, do not
  start it.
- **No revocation of the root token in this ticket.** F8's cutover owns that,
  once both roots run on their own identities.
- No change to which resources either root manages, beyond the `vault_policy`
  resources this ticket deliberately moves.
- **No claim of least privilege.** This identity is scoped, revocable and
  auditable. It is not least-privilege, and no doc, comment or commit message
  in this ticket may say otherwise.

## Requirements & restrictions
1. **Every `vault_policy` resource leaves Terraform.** At the time of writing
   that is `vault_policy.acme_tls_write` (`acme.tf:41`),
   `vault_policy.deployer_applications` (F12) and `vault_policy.human_read`
   (F11). Grep for `resource "vault_policy"` at implementation time rather
   than trusting this list; F11 and F12 may have moved.
2. **They land in an Ansible playbook** using the Vault bootstrap token, in
   the shape of `seed_vault.yml:11-28`. **Add the playbook to
   `bootstrap/justfile:40-49`** — one not named there never runs.
3. **The infrastructure deployer policy grants no `sys/policies/acl` path at
   all**, not even `list`. This is the single most important line in this
   ticket, and Requirement 6 re-proves the plan still passes without it.
4. **`acme-tls-write` moves without a gap.** Import it into Ansible's
   ownership and remove it from Terraform state with `terraform state rm`
   before removing the resource block, so no apply between the two steps
   deletes the live policy. The ACME renewal depends on it.
5. **A dedicated identity, separate from the human and from F12's deployer.**
   Same mechanism as F12 (Q1 there): a `userpass` user, entity and alias. It
   is never attached to the `operator` entity or F11's `humans` group.
6. **Prove the root by running it, twice.** `terraform plan` **and**
   `terraform apply` clean under this identity, with `VAULT_TOKEN` carrying no
   other grant, **after** the policy move. The measured 19-path set above is
   from before the move; the post-move policy is what this ticket ships and
   what must be proven.
7. **Prove the two-step chain is closed.** As this identity: attempt to write
   each existing ACL policy, and attempt to create a group carrying a policy
   the token rewrote. Both must fail at the first step.
8. **Prove the residual ceiling is what the plan says it is.** As this
   identity, create a group carrying an existing policy and confirm it
   succeeds. This one is expected to pass, and recording it is the point: the
   docs claim a bounded ceiling, and an unrun probe is an unsupported claim.
9. **Docs** name the identity, what this root needs and why it differs from
   the applications root, state plainly that it is scoped and **not**
   least-privilege, record the residual ceiling and that it rises when a
   privileged policy is added, and name the follow-up that would close it.
10. Plain language in every doc, comment and commit message
    (`.claude/rules/plain-language.md`).
11. Adversarial review by a sub-agent before this is reported done
    (`.claude/rules/adversarial-reviews.md`).

## Code surface
- `bootstrap/playbooks/seed_vault_policies.yml` **(new)**: the three ACL
  policies, applied with the Vault bootstrap token.
- `bootstrap/justfile` **(edit)**: add the playbook to `:40-49`.
- `deployments/infrastructure/acme.tf` **(edit)**: remove
  `resource "vault_policy" "acme_tls_write"` at `:41`, after
  `terraform state rm`. Anything referencing it moves to a literal name.
- `deployments/infrastructure/deployer_infrastructure.tf` **(new)**: the
  identity — `userpass` user, entity, alias — mirroring
  `auth_userpass.tf:28-56`. **Not** the policy; Ansible owns that.
- F11's and F12's policy resources **(edit)**: removed from Terraform, added
  to the playbook.
- `docs/vault-human-auth.md` **(edit)** or a new sibling doc.

**Do not touch**: `providers.tf` in either root, `.devcontainer/.env`,
`nomad_deploy_role.tf`, `consul_deploy_role.tf`, `oidc.tf`.

## Tests & validation gates
- **Gate**: `just pre_commit` from the repo root (`.loop/config.json:2-4`).
- `terraform validate` and `terraform plan` in both roots.
- `just bootstrap` reaches the new playbook.
- The proof runs are the eval marker at
  `.loop/evals/F13-foundation-infrastructure-deployer.md`.

## Risk assessment
- **Blast radius: the largest in this epic.** Moving `acme-tls-write` between
  owners touches a live policy the ACME renewal depends on, and
  `terraform state rm` is not something the repo does routinely.
- **Reversibility: medium.** The identity and the new playbook are easy to
  drop. Re-importing a policy back into Terraform state is a manual step, so
  a half-finished move is worse than either end state.
- **The failure with real cost is a window where `acme-tls-write` exists in
  neither owner.** Requirement 4 orders the steps for this; verify the live
  policy after every step, not only at the end.
- **The failure with lasting cost is describing this identity as
  least-privilege.** It would be believed, and someone would build on a
  boundary that is not there. Requirement 9 and the eval's docs row exist for
  this.
- **A quieter failure: the new playbook is never added to
  `bootstrap/justfile`.** Then `just bootstrap` silently skips it, the policies
  exist only because Terraform made them before the move, and the next clean
  bootstrap has none. Requirement 2.

## Subtickets (ordered)
1. The Ansible playbook and its `justfile` entry, carrying the three policies.
   Run it and verify all three exist with the right rules. **Do not remove
   anything from Terraform yet** — at this point both owners agree.
2. `terraform state rm` for the three policy resources, then remove the
   blocks. Plan both roots and confirm no destroy is proposed.
3. The infrastructure identity, and the scoped policy without any
   `sys/policies/acl` grant. Plan and apply the root under it.
4. The escalation probes: the closed chain and the residual ceiling.
5. Docs.

## Open questions

**Q1. Why not keep the policies in Terraform and drop `identity/group`
instead?**
*Settled: because the root needs group write.* `vault_identity_group.smoke`
(`oidc.tf:92`) and F11's `humans` group are both Terraform resources in this
root. Dropping group write would break them; dropping policy write costs one
playbook.

**Q2. Does moving policies to Ansible weaken review?**
*Acknowledged, and accepted.* A `vault_policy` resource shows up in
`terraform plan` before it lands; a playbook task does not. The trade is real.
It is accepted because the alternative is an identity that can become root in
two steps, and because Consul's ACL policies already live this way for the
same reason.

**Q3. Should this ticket also move `identity/entity` and `identity/group` out
of Terraform, closing the residual entirely?**
*Settled: no, and this is a deliberate stopping point.* It would mean giving
up three more Terraform resources and rebuilding the OIDC group wiring in
Ansible. The residual it closes is bounded by the set of policies that exist,
none of which is root-equivalent today. File it as a follow-up and revisit if
a privileged policy is ever added.

**Q4. Is `sudo` on `sys/auth/userpass` avoidable?**
*Settled: no.* Measured 2026-07-31: a probe policy with no `sudo` anywhere
created a secrets mount successfully and was refused an auth mount. Only
`sys/auth/*` needs it on Vault 2.0.3; `sys/mounts/*` does not.

## Definition of Done
`deployments/infrastructure/` plans and applies clean under an identity that
holds no `sys/policies/acl` grant, and the two-step escalation chain fails at
its first step. The three ACL policies are owned by an Ansible playbook that
`just bootstrap` actually runs, and `acme-tls-write` was live throughout the
move. The docs state the identity is scoped and not least-privilege, record
the residual ceiling and what raises it, and name the follow-up that would
close it. The root token is not used in the proof.
