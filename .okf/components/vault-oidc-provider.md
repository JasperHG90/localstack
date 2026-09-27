---
type: component
title: Vault's OIDC provider and its clients
description: "How deployments/infrastructure/oidc.tf is put together: one provider named lab, four signing keys, three scopes, seven clients, the assignments that decide who gets in, and a second issuer for identity tokens. Covers the edits a new client makes, the TTL limits Vault enforces, and the template mistakes that pass apply."
tags: [vault, oidc, sso, identity, terraform]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: oidc-tf
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: identity-tf
    resource: git:3ec5d1e:deployments/infrastructure/identity.tf
  - id: secrets-tf
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: applications-services-tf
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: vault-human-auth
    resource: git:3ec5d1e:docs/vault-human-auth.md
  - id: F2-foundation-vault-oidc-provider
    resource: loop:F2-foundation-vault-oidc-provider
  - id: G2-nomad-ui-oidc-login
    resource: loop:G2-nomad-ui-oidc-login
  - id: R5-rollout-memex-oidc-auth
    resource: loop:R5-rollout-memex-oidc-auth
  - id: R6-rollout-memex-human-oidc
    resource: loop:R6-rollout-memex-human-oidc
  - id: F14-foundation-role-taxonomy
    resource: loop:F14-foundation-role-taxonomy
  - id: S3-spike-oidc-version-claims
    resource: loop:S3-spike-oidc-version-claims
---

# Vault's OIDC provider and its clients

Every human single sign-on on this cluster runs through one Vault OIDC
provider, `lab`, declared in `deployments/infrastructure/oidc.tf`. The file
also holds a second, unrelated issuer for identity tokens. The surface a user
sees (issuer URL, claims, which scope a service reads) is
`docs/reference/vault-human-auth.md`. Adding a client step by step is
`docs/how-to/add-a-vault-oidc-client.md`. This page covers how the parts
connect and what breaks quietly.

## The pieces

| Piece | Resource | Notes |
|---|---|---|
| Provider | `vault_identity_oidc_provider.lab` | issuer `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab` |
| Shared key | `vault_identity_oidc_key.lab` | 24h rotation, 24h verification |
| memex key | `vault_identity_oidc_key.memex_human` | 7d rotation, 30d verification |
| Hermes dashboard key | `vault_identity_oidc_key.hermes_dashboard` | 1d rotation, 7d verification |
| Identity-token key | `vault_identity_oidc_key.identity_tokens` | 7d rotation, 30d verification, for the second issuer only |
| Scopes | `groups`, `email`, `openviking` | all three advertised by the provider |
| Clients | `smoke`, `nomad`, `memex`, `oauth2_proxy`, `grafana`, `ov_dash`, `hermes_dashboard` | listed in `local.oidc_provider_client_ids` |

The groups that assignments name (`developer`, `admin`, `openviking-user`,
the `app-*` tiers) are declared in `identity.tf`, described in
[Vault human identity](/components/vault-identity.md).

## What a new client edits

The steps are `docs/how-to/add-a-vault-oidc-client.md`. A client is a section
at the bottom of `oidc.tf`, never a new file, and its one edit outside that
section is appending to `local.oidc_provider_client_ids`. Vault has no
standalone resource for a provider's allowed clients, so that list is inline.
What the steps do not say:

- The key never lists clients inline. That form makes a cycle with the
  client's `key` reference, and the provider forbids mixing it with
  `vault_identity_oidc_key_allowed_client_id` on one key. Forget the
  registration resource and the browser redirect works while the token
  endpoint fails with `client is not authorized to use the key`, so a
  read-only authorize probe cannot catch it.
- Where the secret goes varies. Most confidential clients publish to
  `default/<svc>/oidc` in `secrets.tf`, the smoke client to
  `default/vault/oidc-smoke`, and oauth2-proxy to two paths (dash and
  registry UI). `nomad` has no KV write: its secret passes straight into
  `nomad_acl_auth_method.oidc`.
- Public clients (memex, Hermes dashboard) have no secret. The applications
  root reads their `client_id` back by name through
  `data.vault_identity_oidc_client_creds`
  (`deployments/applications/services.tf`), with no remote state, so the
  infrastructure root must apply first.
- `client_type` and `key` are immutable. Getting either wrong costs a
  destroy, a new `client_id`, and an edit wherever the old id is named.
- The smoke client can be deleted now that real clients exist, but only
  together with its entry in the list.

## Who is allowed in

The header of `oidc.tf` lists four branches: reuse a tier group, add an
`app-*` tier, `allow_all`, or a service group. What the code does today:

| Assignment | Groups | Clients |
|---|---|---|
| `nomad` | `developer` | `nomad` |
| `operators` | `developer`, `admin` | `oauth2_proxy`, `grafana`, `hermes_dashboard` |
| `memex` | `app-memex-admins`, `app-memex-readers` | `memex` |
| `ov-dash` | `openviking-user`, `developer` | `ov_dash` |
| `oidc-smoke` | `oidc-smoke` plus every app tier | `smoke` |

No client uses `allow_all` any more. oauth2-proxy (dash, registry UI) and
Grafana used it until OpenViking consumers got Vault logins. From then on a
person with no operator group could complete a login, and none of those
services filters on groups (oauth2-proxy sets `EMAIL_DOMAINS="*"`). The
`operators` assignment (commit f9c2a68) moved the gate into the provider so
it fails closed for the next consumer. The branch-3 prose in the file header,
the L1 and G1 section comments, and step 3 of the how-to still describe those
clients as `allow_all`.

Bind only your own tier: `local.app_user_group_ids["<tier>"]`. The smoke
assignment uses `local.all_app_user_group_ids`, and a comment marks that line
as not to be copied, because it admits every tier's members.

## Token lifetimes and revocation, per key

Why a client's TTL is capped by its key, why memex keeps a 30-day
`access_token_ttl`, and what rotation does not end are
`docs/explanation/vault-oidc-tokens.md`. The consequence for this file is
that each long session needs its own key, because the shared `lab` key
verifies for 24h:

| Key | Clients | Longest `id_token_ttl` | Lever that stops outstanding tokens |
|---|---|---|---|
| `lab` | smoke, nomad, oauth2-proxy, grafana, ov-dash | 1h (ov-dash 10m) | none per client |
| `memex-human` | memex | 30d | drop the client from `local.oidc_provider_client_ids`, which unpublishes the key ring until the client is added back |
| `hermes-dashboard` | hermes-dashboard | 7d | `terraform apply -replace=vault_identity_oidc_client.hermes_dashboard`, then apply the applications root. Dropping it from the list is weaker: the dashboard caches keys up to an hour, and re-adding the client revives old tokens |
| `identity-tokens` | OpenViking roles | 30d role TTL | none per token |

The drop-from-list lever works for memex only because memex is its key's only
client. R6's reflection records that it was first written as general advice.
The same 10x-rotation cap applies to the identity-token key, whose 30d
verification must cover the longest role TTL it signs.

## The second issuer: identity tokens

`vault_identity_oidc.lab` and the `vault_identity_oidc_role` resources are a
different Vault feature at `/v1/identity/oidc`. Any authenticated caller reads
`identity/oidc/token/<role>` and gets a JWT for its own entity, with no
browser. OpenViking trusts only this issuer and the `openviking` audience,
which `scripts/check_openviking_config.py` asserts against `ov.conf.json` in
the `openviking-config` pre-commit hook.

- `openviking` (humans) templates `ov_account` and `ov_user` from entity
  metadata. `openviking-user`, `developer` and `admin` can read it.
- `openviking_workload` (one per entry in `var.vault_openviking_workloads`)
  writes the account as a literal, because jwt-nomad owns workload entities
  and Terraform cannot stamp metadata on them. The read grant is in
  `machine_roles.tf`, one policy per job.

It has its own key ring so a memex-style revocation on `lab` does not log
everyone out of OpenViking. The issuer setting is cluster-wide but affects
only this second issuer. `docs/explanation/openviking-identity.md` explains
the claim design.

ov-dash joins the two issuers. It gets a provider ID token (with the
`openviking` scope), trades it on the `jwt-lab` auth mount for a Vault token,
and mints an identity token as the person. The mount is in `identity.tf`.

## Traps that pass apply

- **Quoting a template placeholder.** Vault emits fully formed JSON per
  substitution. A quoted `groups` placeholder, or one built with `jsonencode`,
  applies clean because Vault validates against a zero-group entity. At
  issuance the claim is then silently dropped from a signed token. F2 shipped
  this and caught it in review. Quoted `email` or `openviking` placeholders
  fail loudly at apply. Do not "fix" that by adding quotes.
- **Absent metadata renders as `""`.** An entity with no `email` gets an
  empty claim, and Grafana refuses the login at callback. An entity with no
  `ov_account` lands in an OpenViking account named `""`. The ACL on the
  token role, not the mapping, keeps that unreachable.
- **Pointing at the built-in `default` provider.** It allows `["*"]` clients
  and advertises a raw-IP HTTP issuer, so a consumer aimed there works while
  bypassing every assignment. Nothing checks for this.
- **The Nomad selector and claim mapping are one decision.**
  `list_claim_mappings = {groups = "groups"}` must match the selector's
  `list.groups`. A mismatch applies clean and fails at first login with
  `400 no role or policy bindings matched`.
- **The Nomad ACL policy `developer` is Ansible's.** The binding rule names it,
  and `bootstrap/roles/nomad_server/tasks/main.yml` owns it. A Terraform copy
  would give it two owners.

## Enforcement

Nothing tests this file's invariants beyond `terraform validate`, which F2's
reflection notes proves schema and never semantics. The `openviking-config`
hook covers the audience literal. The rest is comments and review.

## History

F2 built the singleton half (key, scope, provider, smoke client) and moved
every consumer client into the ticket that consumes it. G2 added the Nomad
client and its Nomad-side auth method, through the `nomad.manage` provider
([Terraform deployer credentials](/components/deployer-credentials.md)). R5
proved the human memex path impossible with memex 1.1.0 (it verified access
tokens, and Vault's are opaque), so R6 carried it once memex 1.2.0 could
verify an id_token. S3, a spike to check version-dependent OIDC behavior of
MinIO, MLflow, NATS and Postgres, was dropped without running.
