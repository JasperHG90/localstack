---
type: plan
title: 'Plan: postgres-dynamic-credentials'
description: Stand up Vault's Postgres database secrets engine and move Bifrost onto a per-lease Postgres user, the first slice of ADR 0005's rollout.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-19T05:59:15+00:00'
slug: postgres-dynamic-credentials
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# postgres-dynamic-credentials

Relayed from: none

## Intent

Stand up Vault's database secrets engine for Postgres, as
[ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md)
decided and the S2 spike proved, and move the first running consumer,
Bifrost, onto it. Today two running jobs read a static, never-expiring Postgres
password out of KV: `bifrost` (`deployments/applications/services/bifrost.hcl`,
template at lines 86-90, secret `default/bifrost/db` from
`deployments/applications/secrets.tf:203-210`) and `openviking`. Every role
gets its password from `random_password.password` at
`deployments/applications/database.tf:56-67`. After this ticket that count
goes from 2 to 1, and the shape is in place to take the rest one list entry at
a time.

The outcome that shows it worked: Bifrost runs on a user Vault minted for its
lease. `vault lease revoke` on that lease leaves
`select count(*) from pg_roles where rolname = '<user>'` at 0 and a fresh login
with its password refused, the old static `bifrost` password is refused too
(role `bifrost` is `NOLOGIN`), `secret/default/bifrost/db` no longer exists, and
Bifrost's virtual keys survive the restart.

Scope, mirroring the Redis engine in `deployments/infrastructure/database.tf`:

- A dedicated mount `postgres` (not `database`, which the deleted S2 PoC used
  and the applications state may still track), one connection authenticating
  as a dedicated `vault-dbengine-admin` role (CREATEROLE, `ADMIN OPTION` on
  each owner role), never as root `localstack`.
- `local.postgres_dynamic_consumers`, one entry per converted job, driving one
  `vault_database_secret_backend_role`, one `vault_policy` and one
  `vault_jwt_auth_backend_role` each, as `local.redis_cache_consumers` does.
- The six points ADR 0005 says must carry forward: `ALTER ROLE "{{name}}" SET
  ROLE "<owner>"` in every `creation_statements`; `change_mode = "restart"` on
  the credential template (Bifrost's template has no `change_mode`, so the
  default restart already applies); production TTLs (renewal `default_ttl` of
  1h, `max_ttl` 720h, the Redis engine's reasoning: a mint is a restart);
  a dedicated JWT role per job per
  [ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md)
  whose `token_policies` keep `nomad-workloads` for Bifrost's other KV reads;
  the write-only chain from
  [Terraform write-only credential chains](/practices/terraform-write-only-credentials.md)
  (`ephemeral "random_password"`, `password_wo` on both `postgresql_role` and the
  connection, `disable_read = true` on the admin KV copy, `roles` named on the
  admin role, all written in one apply); and failure mode 4, settled by spike
  before build (risk 2).

Placement follows `.claude/rules/terraform-file-layout.md`: engine, admin role
and Vault database roles in `database.tf`, policies and JWT roles in
`machine_roles.tf`, the job in `services.tf`. The admin role must be created by
the `postgresql` provider, which only the applications root has
(`deployments/applications/providers.tf:63-70`), and the write-only chain must
write the role and the connection in one apply, so the engine lands in the
applications root, as the PoC did. That breaks the boundary in
`.okf/architecture/deployment-layers.md` ("Applications root ... does not own
any Vault mount, auth method, policy or role"). This plan is drafted on that
choice and records it as a known exception. The operator chose this
exception on 2026-11-19 over keeping every Vault object in infrastructure; O5
writes it down as ADR 0032.
The `developer` policy in `deployments/infrastructure/identity.tf` gains exact
grants on `sys/mounts/postgres`, `postgres/config/*` and `postgres/roles/*`,
so infrastructure applies first, as it already does.

Postgres consumers today, and what this ticket does with each:

| Consumer | Credential | Anchors | Here |
|---|---|---|---|
| bifrost job | role `bifrost`, KV `default/bifrost/db` | `deployments/applications/services.tf:913-945` (`:934`), `deployments/applications/services/bifrost.hcl:62`, `:86-90`, `:215-226`, `deployments/applications/secrets.tf:203-210` | converted |
| openviking job | role `openviking`, KV `default/openviking/db`, read by two templates | `deployments/applications/services.tf:489-535` (`:513`), `deployments/applications/services/openviking.hcl:317-325`, `:344-354`, `deployments/applications/services/openviking/ov.conf.json`, `deployments/applications/secrets.tf:365-372` | follow-up |
| memex job and its db-migrate prestart (staged, commented out) | role `memex`, KV `default/memex/postgres` | `deployments/applications/services.tf:889-910`, `deployments/applications/services/memex.hcl:44-54`, `:128-135`, `deployments/applications/secrets.tf:26-33` | follow-up, when memex is unstaged |
| phoenix (job retired, role and database kept for traces) | role `phoenix`, KV `default/phoenix/postgres` | `deployments/applications/secrets.tf:15-22` | follow-up decision: no job to convert |
| ducklake_owner, ducklake_reader | static roles, no job | `deployments/applications/database.tf:3-4`, `:97-105` | follow-up decision |
| human copies | KV `default/postgres/<role>` | `deployments/applications/secrets.tf:1-9` | `bifrost` entry removed here, rest untouched |
| postgres-exporter sidecar | root `localstack` | `deployments/infrastructure/services/postgres.hcl:142` | follow-up (old R8) |
| backup-postgres `pg_dumpall` | root, KV `default/backup-postgres/postgres` | `deployments/infrastructure/services/backup-postgres.hcl:36-37`, `deployments/infrastructure/secrets.tf:375-380` | follow-up (old R8) |
| applications root `postgresql` provider | root, ephemeral read of `default/postgres/localstack` | `deployments/applications/providers.tf:63-70`, `deployments/applications/services.tf:16-19` | follow-up (old R8) |
| Postgres server bootstrap | root, set once at first start | `deployments/infrastructure/services/postgres.hcl:74-75`, `deployments/infrastructure/secrets.tf:123-135` | untouched |

Grafana has no Postgres datasource (it only scrapes the exporter through
Prometheus) and MLflow no longer runs, so neither is a consumer.

Spike:postgres-dynamic-credentials/2 found the S2 PoC's KV entry
`secret/default/postgres/vault-dbengine-admin` still live (version 1, an old
admin password for a role that no longer exists). O2's admin KV copy writes
over that path, and the stale versions are destroyed with
`vault kv metadata delete` before the apply so no old password survives.

Out of scope: humans getting credentials from the engine (old S1), rotating the
root password, and the consumers marked follow-up above.

## Problems

- P1: Bifrost logs in to Postgres with a static Terraform-generated password that never expires, so a leaked copy works until someone changes it by hand
- P2: No Vault database secrets engine for Postgres exists, so no job can get a short-lived Postgres user

## Goals

- G1: Bifrost's Postgres credential dies with its lease, and a revoked lease's user can no longer connect
- G2: Converting the next Postgres consumer is one entry in a list plus its jobspec change

## Outcomes

### O1: The `developer` policy grants the `postgres` mount and its config and roles paths
- kind: support
- goal: G2
- fixes: P2
- needs: none
- touches: `deployments/infrastructure/identity.tf`
- checked by: an infrastructure apply, then `vault token capabilities sys/mounts/postgres` on a `localstack login` session reads create, read, update, delete
- seen by: operator

### O2: A `postgres` database engine mints users as `vault-dbengine-admin`, one role per entry in `local.postgres_dynamic_consumers`
- kind: support
- goal: G2
- fixes: P2
- needs: O1
- touches: `deployments/applications/database.tf`, `deployments/applications/secrets.tf`
- checked by: `vault read postgres/config/postgres` shows username `vault-dbengine-admin`; `terraform state pull` holds zero copies of the admin password; `vault read postgres/creds/bifrost` mints a user whose `current_user` is `bifrost`
- seen by: operator

### O3: Each converted job gets its own Vault policy and JWT role reading only its `postgres/creds/<job>` path
- kind: support
- goal: G2
- fixes: P2
- needs: O2
- touches: `new:deployments/applications/machine_roles.tf`
- checked by: `vault read auth/jwt-nomad/role/postgres-bifrost` shows `bound_claims` on `nomad_job_id = bifrost` and both `nomad-workloads` and the creds-read policy
- seen by: operator

### O4: Bifrost reads a minted Postgres user and its static password is gone
- kind: behaviour
- goal: G1
- fixes: P1
- needs: O2, O3
- touches: `deployments/applications/services.tf`, `deployments/applications/services/bifrost.hcl`, `deployments/applications/secrets.tf`, `deployments/applications/database.tf`
- checked by: on the live cluster, Bifrost's alloc is healthy and its virtual keys list; `vault lease revoke` on its lease leaves 0 rows in `pg_roles` for the user and a fresh login refused; the old `bifrost` password is refused; `vault kv get secret/default/bifrost/db` is not found; `select count(*) from pg_class c join pg_roles r on r.oid = c.relowner where r.rolname like 'v-%'` in the bifrost database is 0
- seen by: operator

### O5: The knowledge bundle and docs say the engine is built and where it lives
- kind: support
- goal: G2
- fixes: P2
- needs: O4
- touches: `.okf/components/postgres.md`, `.okf/components/vault-secrets-engines.md`, `.okf/proposals/postgres-dynamic-credentials.md`, `.okf/architecture/deployment-layers.md`, `.okf/components/terraform-roots.md`, `docs/explanation/workload-identity.md`, `.okf/summary.md`, `new:.okf/decisions/0032-the-postgres-database-engine-lives-in-the-applications-root.md`
- checked by: `kmctl check` passes and `deployment-layers.md` names the applications-root engine as a known exception in its owns table and Depicts section
- seen by: nobody

## Could invalidate this plan

- Risk 1 (operator fork, no spike answers it): the engine, its admin role and
  the per-job Vault policies and JWT roles land in the applications root,
  which `.okf/architecture/deployment-layers.md` says owns no Vault mount,
  policy or role. The alternative keeps every Vault object in infrastructure:
  infrastructure mints the admin password and writes it write-only to KV and to
  the connection, and applications reads it back ephemerally to set
  `password_wo` on the Postgres role. That splits the write-only chain across
  two roots, so the connection cannot verify on a first apply and every
  rotation needs both roots in order. If the operator rejects the exception,
  O2 and O3 move files and O1 grows, and the plan needs a rewrite before build.
  The operator chose the applications-root exception on 2026-11-19; their
  acceptance is recorded with `loopctl plan accept`.
- Risk 2 (spike): ADR 0005's untested failure mode 4. If a minted user with
  `ALTER ROLE ... SET ROLE "bifrost"` cannot run Bifrost 2.3.1's startup
  migrations against tables `bifrost` already owns, or Bifrost's driver resets
  the role (`RESET ROLE`, `DISCARD ALL`) so new objects land on the minted user
  and revocation silently fails, Path A does not fit this consumer.
- Risk 3 (spike): the write-only chain the S2 PoC used (`ephemeral
  "random_password"`, `password_wo` on `postgresql_role` at
  `cyrilgdn/postgresql ~>1.26.0`, `password_wo` on the connection and
  `data_json_wo` with `disable_read` at `hashicorp/vault ~>5.3.0`) must still
  validate and apply from a `localstack login` session, and the PoC's leftovers
  (the `database/` mount, `vault-dbengine-admin` role, its KV entry, any
  `database-secrets-poc` address in applications state) must not collide. If
  the chain no longer works, the admin password lands in Consul-backed state
  and the practice's exception for keeping the engine in Terraform collapses.
  Settled: spike:postgres-dynamic-credentials/3 applied the whole chain in one
  apply on vault 5.3.0, postgresql 1.26.0 and random 3.9.0 from a
  `localstack login` session, with 0 copies of the password in state and a
  clean second plan. spike:postgres-dynamic-credentials/2 found no colliding
  mount, role or state address, and one stale KV entry O2 now removes. Not
  covered: the Consul backend and `ADMIN OPTION` grants, which build checks.
