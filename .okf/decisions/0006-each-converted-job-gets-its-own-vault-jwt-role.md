---
type: decision
title: "ADR 0006: Each job that mints database credentials gets its own Vault JWT role, and the shared nomad-workloads policy is not widened"
description: "A job reading database/creds/* names a dedicated JWT role whose policy also carries its KV grants. Widening nomad-workloads was one line of Ansible but would let every workload mint database users."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, vault, workload-identity, postgres, redis]
status: stable
sources:
  - id: postgres-vault-dynamic-creds-spike
    resource: .okf/proposals/postgres-dynamic-credentials.md
  - id: jwt-roles
    resource: deployments/infrastructure/machine_roles.tf
  - id: redis-consumers
    resource: deployments/infrastructure/database.tf
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

## Correction, 2026-10-19

mlflow and phoenix no longer run. A conversion today covers memex's
`db-migrate` prestart and the other running jobs with a role in
`deployments/applications/database.tf`: bifrost and openviking. The phoenix role and its KV entry
outlive the job (`deployments/applications/secrets.tf`), and mlflow's bucket
outlives its job (`deployments/applications/storage.tf`).

The Redis cache's per-consumer JWT roles are
`vault_jwt_auth_backend_role.redis_cache` in
`deployments/infrastructure/machine_roles.tf`, one per entry in
`local.redis_cache_consumers`. `deployments/infrastructure/database.tf` holds
that list and the comment that cites this record.

## Correction, 2026-11-24

mlflow's bucket no longer outlives its job. It was a MinIO bucket, and
`deployments/applications/storage.tf` dropped it with every other `minio_*`
resource when MinIO was removed
([ADR 0018](/decisions/0018-remove-minio.md)). Its data went with the
`minio_data` volume. Nothing under `deployments/` names mlflow except two
comments in the oauth2-proxy jobspecs. The phoenix role and its KV entry
still outlive their job (`deployments/applications/secrets.tf`,
`deployments/applications/database.tf`).
