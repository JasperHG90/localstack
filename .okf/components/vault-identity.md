---
type: component
title: Vault human identity
description: "How deployments/infrastructure/identity.tf builds human access: the userpass and jwt-lab auth mounts, entities and their aliases, the developer, admin, openviking-user and app-user groups, and the TOTP Login MFA resources. Records which membership Terraform owns and which it does not, and the grants no code review would have found."
tags: [vault, identity, userpass, groups, mfa, terraform]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: identity-tf
    resource: git:3ec5d1e:deployments/infrastructure/identity.tf
  - id: oidc-tf
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: variables-tf
    resource: git:3ec5d1e:deployments/infrastructure/variables.tf
  - id: root-justfile
    resource: git:3ec5d1e:justfile
  - id: vault-mfa-sh
    resource: git:3ec5d1e:scripts/vault_mfa.sh
  - id: F2-foundation-vault-oidc-provider
    resource: loop:F2-foundation-vault-oidc-provider
  - id: F11-foundation-human-read-role
    resource: loop:F11-foundation-human-read-role
  - id: F14-foundation-role-taxonomy
    resource: loop:F14-foundation-role-taxonomy
  - id: F14-foundation-app-user-groups
    resource: loop:F14-foundation-app-user-groups
  - id: R6-rollout-memex-human-oidc
    resource: loop:R6-rollout-memex-human-oidc
---

# Vault human identity

`deployments/infrastructure/identity.tf` decides who a person is in Vault and
what their groups grant. Machine identity is
[the workload identity chain](/components/workload-identity-chain.md), and the
SSO clients that read these groups are
[Vault's OIDC provider](/components/vault-oidc-provider.md). What each role
is for is `docs/reference/cluster-roles.md`, and why they are shaped that way
is `docs/explanation/cluster-roles.md`. Neither is repeated here.

## The pieces

| Section of `identity.tf` | What it creates |
|---|---|
| human auth | `vault_auth_backend.userpass`, the operator's password (`random_password`), user (`vault_generic_endpoint`), entity and alias |
| login MFA | `vault_identity_mfa_totp.lab`, `vault_identity_mfa_login_enforcement.userpass` |
| openviking consumers | one userpass user, entity and alias per entry in `var.vault_openviking_consumers`, the `openviking-user` policy and group |
| jwt-lab | `vault_jwt_auth_backend.lab`, the `ov-dash` role, one jwt-lab alias per person |
| developer | `vault_policy.developer`, `vault_identity_group.developer` |
| admin | `vault_policy.admin`, `vault_identity_group.admin` |
| app-user scaffold | `local.app_user_groups`, `local.app_user_group_members`, `vault_identity_group.app_user`, `local.app_user_group_ids` |

Passwords are published to KV by `secrets.tf` (`default/vault/operator`, and
one entry per OpenViking consumer).

## How a login becomes group membership

A userpass login carries an `entity_id` only because an alias on the userpass
accessor names the entity. The group then attaches its policy to the entity,
so the policy shows in a token's `identity_policies`, never in `policies`
(which holds only `default`). F11's reflection records an eval row that
checked `policies` and would have failed every correct login.

Users are written through `vault_generic_endpoint` because provider 5.3.0
has no userpass-user resource. `token_policies = []` on every user: the
account exists to get an identity, and all privilege arrives through groups.
Each alias `depends_on` its user, since the alias only makes sense once the
login exists.

Entity metadata is load-bearing. `email` is the only source for the `email`
claim, and Grafana refuses an empty one. `ov_account` and `ov_user` feed the
OpenViking claims. A missing key renders as `""`, and nothing refuses it.
Writing one metadata key by hand replaces the whole map: F14's probe evicted
`managed_by` and `kind` this way, and the next apply put them back, which
hid a second eviction.

## Who owns membership

| Group | Members set by | Why |
|---|---|---|
| `developer` | Terraform (`member_entity_ids`) | one entry per person, reviewed in a diff |
| `admin` | a `vault write` (`external_member_entity_ids = true`) | joined and left mid-incident, so no apply may revert it |
| `app-*` tiers | Terraform (`local.app_user_group_members`) | a tier list should be reviewable, and a hand-added member is reverted |
| `openviking-user` | Terraform, from `var.vault_openviking_consumers` | |

`admin` has the cost: staying in it after an incident shows in no plan.
`just admin_status`, `admin_join` and `admin_leave` in the root `justfile`
read the member list and edit only your own id, because the API only
replaces the whole list and `identity/group-member-entity-ids` does not exist
on this Vault. F14's first `leave` command emptied the group.

## The policies, and what they do not bound

`developer` is written as an exact-path list, but its holder can write
`identity/*` and `sys/policies/acl/*`, so it reaches anything short of the
`root` policy in a few commands. The comment says so and asks that no comment
call it a boundary. It is also the policy both Terraform roots run under
([Terraform deployer credentials](/components/deployer-credentials.md)).

F11 built it by running both roots under candidate policies until they
stopped returning 403. Three grants came only from that measurement:

- `auth/token/create`, because the Vault provider mints a child token before
  it reads anything.
- `sys/mounts/secret/tune` and `sys/mounts/auth/userpass/tune`, because mount
  paths are exact matches and do not cover their own tune subpath.
- `sudo` on `sys/auth/userpass/tune`, the CLI's form. Denied on the
  provider's form, provider 5.3.0 reports success and changes nothing
  (hashicorp/terraform-provider-vault#2983).

A new mount always needs its own `sys/mounts/<path>` line. There is no
wildcard, which is why `database.tf` orders `vault_mount.redis` after this
policy.

`admin` is `path "*"` plus every path the `default` policy names, restated
because Vault picks the most specific match and a default path would
otherwise cap the holder. Three of those are templated or wildcarded and
must be copied verbatim, never retyped.

Both policies are heredocs, so their `#` comments are stored in Vault. Editing
a comment rewrites the policy on the next apply. That once armed the 403 in
[Terraform deployer credentials](/components/deployer-credentials.md). Stale
file names inside them (`redis_secrets_engine.tf`, `nomad_oidc.tf`) stay stale
for that reason (`.claude/rules/terraform-file-layout.md`).

## The app-user scaffold

F2 shipped `local.app_user_groups` empty and memex (R6) is its only consumer,
with `app-memex-admins` and `app-memex-readers`. The groups carry
`policies = []`: they exist to be named by an OIDC assignment. Consumers read
`local.app_user_group_ids`, keyed by tier. An earlier revision exposed one
flat list, which let the first consumer's assignment admit the second
consumer's members with no change in the first consumer's code. R6 chose
these tiers over reusing break-glass `admin`, which would have meant living
in break-glass for daily memex use. `docs/how-to/add-an-app-user-tier.md` is
the procedure.

The original plan for the tier contract,
`F14-foundation-app-user-groups`, failed plan review and was dropped.
`F14-foundation-role-taxonomy` built the `admin` group and this scaffold.

## OpenViking consumers and the jwt-lab mount

A consumer is defined by what they are not in: no `developer`, no `admin`, no
tier. Their one grant is reading `identity/oidc/token/openviking`. The
operator reaches the same path through `developer`'s `identity/*`, and is not
added to `openviking-user` on purpose.

`jwt-lab` is a second human mount holding no credential of its own. ov-dash
posts a provider ID token there and gets a five-minute Vault token for the
person. Its traps:

- `jwks_url` is plaintext loopback (`127.0.0.1:8200`), because a discovery
  URL would have to be the public HTTPS one byte for byte and trust the edge
  certificate. `bound_issuer` carries the public issuer, since that is what
  the provider stamps.
- The role's `user_claim` is `ov_user`, so the jwt-lab aliases are named by
  `ov_user`, not by username. For the operator those differ (`operator` and
  `jasper`).
- A login with no matching alias does not fail. Vault creates a fresh entity
  in no group, the mint answers 403 one hop later, and the invented alias
  makes the next apply fail with "already exists". Apply the mount, role and
  aliases together.
- Two people sharing one `ov_user` would collide. A `precondition` on
  `vault_identity_entity_alias.ov_dash_consumer` refuses the plan. It is the
  only invariant in this file a tool enforces.

## Login MFA

TOTP is enforced on the userpass mount accessor. Why the accessor, and not an
entity or a mount type, is
[ADR 0011](/decisions/0011-login-mfa-enforcement-names-the-userpass-mount.md).
In short, naming the operator entity also challenged the jwt-lab trade, which
cannot answer a prompt.

The per-person secret is not in Terraform, because it is the second factor.
`just mfa_enroll <user>` runs `scripts/vault_mfa.sh`, which asks Vault for
the QR ([ADR 0010](/decisions/0010-vault-generates-each-totp-qr.md)). Its
measured API traps are the
[TOTP enrollment practice](/practices/vault-totp-enrollment.md), and
`just mfa_test` runs it against a fake Vault. The enforcement is mount-wide,
so every person in `var.vault_openviking_consumers` must be enrolled before
it applies, or they cannot log in at all. There is no enrollment page on dash
([ADR 0012](/decisions/0012-no-mfa-enrollment-app-on-dash.md)). The rollout
state and inventory are the
[MFA handoff proposal](/proposals/vault-login-mfa.md). The root token
bypasses all of it.

## History

F2 created the userpass mount so a human could hold an entity-bearing token.
Before it, only `jwt-nomad/` and `token/` existed. F11 added `developer` and
moved daily work off the root token. F14 added `admin` and the scaffold, R6
the memex tiers, and the OpenViking work the consumers and jwt-lab. The MFA
resources came in commits 8500637 and 59ad3b3. No audit device is enabled,
so none of these groups gives attribution.
