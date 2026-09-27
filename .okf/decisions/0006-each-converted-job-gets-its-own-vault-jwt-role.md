---
type: decision
title: "ADR 0006: Each job that mints database credentials gets its own Vault JWT role, and the shared nomad-workloads policy is not widened"
description: "A job reading database/creds/* names a dedicated JWT role whose policy also carries its KV grants. Widening nomad-workloads was one line of Ansible but would let every workload mint database users."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, vault, workload-identity, postgres, redis]
status: stable
decision_status: Accepted
decided_on: 2026-08-03
sources:
  - id: postgres-vault-dynamic-creds-spike
    resource: git:3ec5d1e:docs/postgres-vault-dynamic-creds-spike.md
    last_modified: 2026-09-03
---

# ADR 0006: Each job that mints database credentials gets its own Vault JWT role, and the shared nomad-workloads policy is not widened

- Status: Accepted
- Date: 2026-08-03

> Written retrospectively from `docs/postgres-vault-dynamic-creds-spike.md`, dated 2026-09-03.

## Context

A Nomad task performs a single JWT login and holds a single Vault token, so
naming a dedicated role in `vault { role = ... }` REPLACES `nomad-workloads`
rather than adding to it. The PoC role works around this the way the `acme` role
in `machine_roles.tf` does,
by listing `nomad-workloads` in its own `token_policies`.

In the spike's negative control, a job with a bare `vault {}` blocked on
`Missing: vault.read(database/creds/s2-poc)` and never started. That is
what makes the
dedicated JWT role load-bearing rather than decorative, and it is why the
shared Ansible policy did not need widening.

## Decision

For R3 this is a real cost. Every converted job needs a dedicated JWT role
whose policy carries both the new `database/creds/*` read and the KV grants the
job still uses: memex's `db-migrate` prestart, mlflow, phoenix. The alternative,
widening the shared `nomad-workloads` policy, is one line of Ansible and gives
every workload on the cluster the ability to mint database users.

Take the per-job cost. It is bounded by the number of jobs converted, and F3
already carries the pattern.

## Consequences

Every converted job costs a `vault_jwt_auth_backend_role` and a policy,
and its `claim_mappings` must mirror the shared role
(`docs/explanation/workload-identity.md`, "The one-token rule"). The Redis
cache engine in `deployments/infrastructure/database.tf` pays this cost with
one role per consumer, and cites this reasoning for rejecting a single shared
role gated only on the namespace.
