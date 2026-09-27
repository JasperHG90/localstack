---
type: decision
title: "ADR 0012: TOTP enrollment has no app on dash"
description: "Nobody builds an enrollment page behind SSO, because an unenrolled person cannot complete the Vault login that reaching dash requires. Vault's own UI is the GUI after enrollment."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, vault, mfa, dash]
status: stable
decision_status: Accepted
decided_on: 2026-09-12
sources:
  - id: vault-2fa
    resource: git:3ec5d1e:docs/vault-2fa.md
    last_modified: 2026-09-12
---

# ADR 0012: TOTP enrollment has no app on dash

- Status: Accepted
- Date: 2026-09-12

> Written retrospectively from `docs/vault-2fa.md`, dated 2026-09-12.

## Context

People reach the cluster's apps through a Vault login, and once the
enforcement is on, that login requires an enrolled second factor. An
enrollment page on dash was the alternative to enrolling people from the
operator's shell.

## Decision

**No enrollment app on dash.** dash sits behind oauth2-proxy, which
authenticates against the `lab` provider, so reaching dash requires a completed
Vault login. Once enforcement is on, an unenrolled person cannot complete that
login and so never reaches dash. Every app behind SSO has this shape, and the
only people who could use such an app are the ones who do not need it.
Enrollment has to happen at the one moment an unenrolled user is talking to
Vault, which is the login Vault is refusing. Vault's own UI at
`vault.lab.orangecluster.nl` is the GUI for everything after that.

## Consequences

Enrollment stays with the operator (`just mfa_enroll`), per
[ADR 0010](/decisions/0010-vault-generates-each-totp-qr.md). Any future
self-service enrollment has to run at the Vault login itself, not in an app
behind it.
