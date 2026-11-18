---
type: decision
title: "ADR 0031: The lab-auth action picks the Tailscale identity from the OIDC subject format"
description: "The lab-auth action reads the job OIDC sub and uses the immutable-subject Tailscale identity for repositories created after 2026-07-15 and the original identity otherwise, so no caller passes Tailscale inputs."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-18T13:20:27Z
status: stable
sources:
  - resource: ".github/actions/lab-auth/action.yml"
  - resource: "cli/tests/test_lab_auth_action.py"
---

# ADR 0031: The lab-auth action picks the Tailscale identity from the OIDC subject format

## Context

[ADR 0027](/decisions/0027-ci-reaches-the-lab-through-a-public-lab-auth-action-and-per-caller-vault-roles.md)
joins a job to the tailnet through one Tailscale federated identity with
subject `repo:JasperHG90/*:environment:lab`. GitHub gives repositories created
after 2026-07-15 an immutable OIDC subject,
`repo:JasperHG90@8079803/<repo>@<id>:environment:lab`, where `8079803` is the
operator's account ID. That subject has `@8079803` where the identity's
pattern wants `/`, so those repositories got a 403 at the token exchange.
`JasperHG90/loop-engineering-harness` is one. `localstack` is older and keeps
the name-only subject.

On 2026-11-18 the operator created a second identity in the Tailscale console,
subject `repo:JasperHG90@8079803/*:environment:lab`, scope Auth Keys write, tag
`tag:ci`, client ID `T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL`. Old repositories
still need the first identity and new ones need the second.

## Decision

The action's `tailscale-identity` step reads `sub` from a GitHub OIDC token
with an audience nothing trusts, `lab-auth-subject-only`, before it joins. A
subject that starts `repo:JasperHG90@8079803/` gets the second identity, and
any other subject gets the first. The audience is
`api.tailscale.com/<client ID>`. `tailscale-client-id` and
`tailscale-audience` now default to empty and still override when a caller
passes them.

spike:lab-auth-immutable-subject/1 showed the step working in
`JasperHG90/lab-auth-probe`. The `lab` job picked the second identity and
joined, and a job without `environment: lab` got a 403.

Rejected:

- **A default of the second identity, with old repositories passing the first
  identity's values.** Every older repository connected later would need two
  inputs it cannot guess, and a missed one fails as a bare 403.
- **Switching each new repository back to the name-only subject** through
  `actions/oidc/customization/sub`. It is a manual step per repository, and it
  gives up the protection the immutable subject adds: a deleted or renamed
  repository's name, taken by someone else, no longer matches.
- **One identity with a wider subject pattern.** The two formats share only
  the prefix `repo:JasperHG90`, and a pattern that broad also matches any
  account whose name starts with it, such as `JasperHG90x`.

## Consequences

- This amends ADR 0027's consequence that an immutable-subject repository
  needs its own identity. One second identity, made once, covers all of them,
  and no caller passes Tailscale inputs.
- The step fetches a second OIDC token per run. It is masked and sent nowhere.
- The step matches on the account ID, not the name, so renaming the account
  needs no change here. Moving repositories to another owner does.
- `cli/tests/test_lab_auth_action.py` runs the step against both subject
  formats and against explicit inputs.
