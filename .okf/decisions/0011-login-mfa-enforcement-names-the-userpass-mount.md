---
type: decision
title: "ADR 0011: Login MFA is enforced on the userpass mount accessor, not on an entity or a mount type"
description: "The TOTP login enforcement names vault_auth_backend.userpass.accessor. Naming the operator entity challenged the ov-dash trade on jwt-lab, and naming the mount type would have widened it to jwt-nomad."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, vault, mfa, identity]
status: stable
decision_status: Accepted
decided_on: 2026-09-12
sources:
  - id: vault-2fa
    resource: git:3ec5d1e:docs/vault-2fa.md
    last_modified: 2026-09-12
---

# ADR 0011: Login MFA is enforced on the userpass mount accessor, not on an entity or a mount type

- Status: Accepted
- Date: 2026-09-12

> Written retrospectively from `docs/vault-2fa.md`, dated 2026-09-12.

## Context

Vault is the OIDC provider for humans here, so a person reaches an app by
completing a Vault login first. Six clients are registered with the `lab`
provider (`deployments/infrastructure/oidc.tf`): the smoke client, nomad,
memex, oauth2-proxy (which fronts dash), grafana and ov-dash. A second factor
on the Vault login therefore reaches all six without touching any of them.

An enforcement on the userpass mount also covers
anything that posts a username and password straight at
`auth/userpass/login/*`. There were two of those, and both are settled.

**`localstack login`** raised unless the reply carried `auth.client_token`, and
Vault answers an enforced mount with HTTP 200, an `auth` block whose
`client_token` is empty, and the challenge at `auth.mfa_requirement`. The CLI
reported that as "returned no token. Check the username", which sends the
reader looking for a typo that is not there. It now raises `MFARequired`,
prompts for the passcode, and finishes at `sys/mfa/validate`. This mattered
more than it looked: all three `mfa_*` recipes open with
`eval "$(localstack env)"`, so an unfixed CLI would have stranded the operator
with no way to reach `just mfa_reset` once a session lapsed.

**ov-dash** posted at the same mount under `AUTH_MODE=vault-userpass`, and it
cannot answer a challenge: there is no MFA code in the image, so an enforced
login fails with "Vault accepted the login but returned no token". It no longer
posts there. Under `AUTH_MODE=vault-oidc` a person signs in at Vault's page,
ov-dash trades the ID token it gets back for a Vault token on the `jwt-lab`
mount, and mints the OpenViking token as them. No password reaches the
dashboard, and nothing challenges it.

## Decision

`auth_method_accessors = [vault_auth_backend.userpass.accessor]` covers every
human login that carries a password, including the one Vault runs behind its
own OIDC provider page. The factor is asked once per Vault session, and every
app behind SSO inherits it.

**The enforcement must not reach `jwt-lab`.** That trade is a login too, and
ov-dash can no more answer a challenge there than at the password form. Naming
the userpass accessor keeps it out. Naming an entity would not: Vault matches
an enforcement wherever that entity authenticates, mount included, so
`identity_entity_ids = [operator]`, which is what this was, challenges the
trade and strands the operator at the first hop while sparing everyone outside
the list. The scoping is not a widening of the old one for its own sake. It is
the shape the chain requires.

**The enforcement names the mount accessor, not the mount type.** Vault matches
an enforcement's targets as a union, so every target added widens what is
enforced. Naming `vault_auth_backend.userpass.accessor` keeps `jwt-nomad`
outside it, and workload identity is unaffected.

## Consequences

Every human login that carries a password meets the challenge once per
Vault session, and the `jwt-lab` trade and `jwt-nomad` workload logins do not.
Adding an entity id back to the enforcement enforces on the union of targets,
so the enforcement has to keep naming only the accessor. What the enforcement
still does not cover is listed in `docs/explanation/vault-login-mfa.md`.
