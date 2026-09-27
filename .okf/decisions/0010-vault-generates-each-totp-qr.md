---
type: decision
title: "ADR 0010: Vault generates each person's TOTP QR, and self-enrollment stays off"
description: "Enrollment is an admin-generate run per person through just mfa_enroll. enable_self_enrollment was rejected because no Terraform provider exposes it and it guards a password stolen after enrollment only."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, vault, mfa]
status: stable
decision_status: Accepted
decided_on: 2026-09-11
sources:
  - id: vault-2fa
    resource: git:3ec5d1e:docs/vault-2fa.md
    last_modified: 2026-09-12
---

# ADR 0010: Vault generates each person's TOTP QR, and self-enrollment stays off

- Status: Accepted
- Date: 2026-09-11

> Written retrospectively from `docs/vault-2fa.md`, dated 2026-09-12.

## Context

Enforcing TOTP before a person holds a secret locks that account out of
userpass, so every person has to be enrolled before the enforcement lands.
Vault can either generate each secret on an operator's request, or hand the
QR back itself during the blocked login.

## Decision

**Vault generates the QR, one person at a time.** The alternative was
`enable_self_enrollment`, which makes Vault hand the QR back during the blocked
login. Vault 2.0.3 supports the flag. No Terraform provider exposes it: absent
from the pinned 5.3.0 and from the current 5.11.0, both checked on 2026-09-11.
Setting it would take a `vault_generic_endpoint` write restating the method's
whole config, because a POST to the method path resets every unsent field to
its default. For two people, enrolling once costs less than carrying that
workaround. Self-enrollment also lets anyone holding a password bind their own
authenticator, so it guards a password stolen after enrollment and not before.

## Consequences

Enrollment is an operator task per person, run with `just mfa_enroll`
before the enforcement is applied, and a lost phone is `just mfa_reset`. The
traps in that path are in
[Traps in Vault TOTP enrollment](/practices/vault-totp-enrollment.md).
Revisit if a provider release exposes `enable_self_enrollment`, or if the
number of people grows past what one-at-a-time enrollment serves.
