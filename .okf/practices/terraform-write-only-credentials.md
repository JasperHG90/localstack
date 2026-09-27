---
type: practice
title: Terraform write-only credential chains
description: "Three defects that pass terraform validate and cost real time in the Postgres spike: ephemeral values differ across applies, vault_kv_secret_v2 reads the secret back into state, and postgresql_role strips memberships granted by postgresql_grant_role."
tags: [terraform, vault, postgres, state, lessons]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: postgres-vault-dynamic-creds-spike
    resource: git:3ec5d1e:docs/postgres-vault-dynamic-creds-spike.md
    last_modified: 2026-09-03
---

# Terraform write-only credential chains

Measured while building the Postgres dynamic-credentials spike,
[the proposal](/proposals/postgres-dynamic-credentials.md), on 2026-08-03.

## A Terraform trap worth knowing about

Three defects in the write-only credential chain cost real time here, and all
three pass `terraform validate`:

**An ephemeral value is not shared across applies.** `ephemeral
"random_password"` is regenerated every run and persisted nowhere, so consumers
that write in different applies get different passwords. Creating the Postgres
role in one targeted apply and the Vault connection in the next produced
`failed SASL auth ... password authentication failed`. `verify_connection`
caught it, which is a good argument for never setting that to false. An
unchanged `_wo_version` on an existing resource really is a no-op. The hazard
is any resource that writes: one being created, or one whose version moved.

**`vault_kv_secret_v2` reads the secret back by default.** The computed `data`
attribute then holds the plaintext, putting the credential into the
Consul-backed state through the back door. `disable_read = true` is required,
not optional.

**`postgresql_role` fights `postgresql_grant_role`.** With `roles` left unset,
the provider reconciles the role's memberships to the empty set on every update,
silently stripping the membership granted elsewhere. Minting then failed with
`permission denied to grant role "memex" (SQLSTATE 42501)` at the next
`vault read`, long after the apply that broke it reported success. Naming the
membership in both places keeps them agreeing.

With all three handled, the state is clean: `terraform state pull` over 233 KB
contains zero occurrences of the admin password.

That last point is what justifies keeping this engine's mount and config in
Terraform at all. F5 and F6 hand both to Ansible whenever a Vault engine needs
a privileged external credential
(`deployments/infrastructure/machine_roles.tf`, the deployer's Consul role),
precisely to keep
that credential out of the Consul-backed state. The write-only chain achieves
the same end, so the exception is earned rather than assumed. It is earned only
while the chain stays intact: swap the ephemeral for a `random_password`
resource and the password lands in state, and the exception collapses.
