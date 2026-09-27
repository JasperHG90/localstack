---
type: component
title: Postgres
description: "One PostgreSQL 18 server with pgvector on firebat, split across both Terraform roots: the infrastructure root runs the job, its exporter sidecar and the root credential, and the applications root creates every database and role through that root credential. Every login is still a static password, and the golang-migrate folder is a scaffold nothing runs."
tags: [postgres, pgvector, database, vault, terraform, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: postgres-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/postgres.hcl
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: app-database
    resource: git:3ec5d1e:deployments/applications/database.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: app-providers
    resource: git:3ec5d1e:deployments/applications/providers.tf
  - id: migrations
    resource: git:3ec5d1e:applications/migrations/justfile
  - id: S2-spike-postgres-vault-creds
    resource: loop:S2-spike-postgres-vault-creds
  - id: R8-rollout-postgres-root-consumers
    resource: loop:R8-rollout-postgres-root-consumers
  - id: backup-swap-memex-for-openviking
    resource: loop:backup-swap-memex-for-openviking
---

# Postgres

One server holds every relational database on the cluster. It is built in two
Terraform roots, and the second cannot plan until the first has applied.

## The pieces

| Piece | Where |
| --- | --- |
| Job `postgres`, pinned to firebat, image `docker.io/pgvector/pgvector:pg18-trixie` | `deployments/infrastructure/services/postgres.hcl` |
| Host volume `postgres` (10 to 100 GiB, firebat) | `nomad_dynamic_host_volume.postgres` in `deployments/infrastructure/services.tf` |
| Firewall: 5432 from `192.168.0.0/16`, 9187 from Prometheus (.47) only | `local.firewall_rules` in the same file |
| Root login `localstack`, password `random_password.postgres_root` | KV `default/postgres/localstack`, `deployments/infrastructure/secrets.tf` |
| Exporter sidecar `postgres-exporter`, v0.20.1, port 9187 | second task in `postgres.hcl` |
| Roles, databases, extensions, reader grants | `deployments/applications/database.tf` |
| Per-consumer password copies | `deployments/applications/secrets.tf` |

The server registers in Consul as `postgres-db`. The applications root finds
it that way: `data.consul_service.postgres` supplies the host for the
`postgresql` provider, and `ephemeral.vault_kv_secret_v2.postgres_admin`
supplies the root login (`deployments/applications/services.tf`,
`deployments/applications/providers.tf`). So the apply order is fixed:
infrastructure first, until the job is running and registered, then
applications.

## What the applications root creates

`local.roles` and `local.databases` in `deployments/applications/database.tf`
drive everything. Each role gets a `random_password`, a `postgresql_role` with
login, and a KV entry at `default/postgres/<role>`. Each database gets an owner,
`lc_collate = "C"`, and its listed extensions. Today's set:

- `ducklake`, owned by `ducklake_owner`, with `ducklake_reader` granted
  `SELECT` on tables in `public`.
- `memex` and `openviking`, each with the `vector` extension. The openviking
  database has its own history, in
  [The OpenViking database](/components/openviking-database.md).
- `phoenix`, kept after the phoenix job was retired so the stored traces
  survive. Its KV entry stays for the same reason.
- `bifrost`, an empty database Bifrost migrates itself for its config store.

A job cannot read `default/postgres/<role>`. The `nomad-workloads` Vault
policy only grants a job `secret/data/<namespace>/<job_id>/*`
(`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`), so
every consumer that runs gets a second copy of its password under its own
prefix: `default/memex/postgres`, `default/phoenix/postgres`,
`default/bifrost/db`, `default/openviking/db`. The `default/postgres/*`
entries are for people.

## Three consumers log in as root

The exporter sidecar (its `DATA_SOURCE_NAME` template), the nightly
`backup-postgres` job (through its own copy at
`default/backup-postgres/postgres`), and the applications root's `postgresql`
provider all authenticate as `localstack`. R8 (a stub ticket) owns moving them
off. Until it does, the root password cannot rotate without breaking all
three at once, which is why S2 built a separate admin role for Vault instead
of handing Vault this one.

## Invariants and what enforces them

- **The root password is set once, at first start.** The image applies
  `POSTGRES_USER` and `POSTGRES_PASSWORD` only when `PGDATA` is empty. Replacing
  `random_password.postgres_root` rewrites both KV copies but leaves the
  server's real password alone, and every root consumer then fails to log in.
  Nothing checks this.
- **The `vector` extension depends on the image.** `postgresql_extension`
  creates it in `memex` and `openviking`, and only the pgvector image ships
  the library. Moving to a stock postgres image breaks every vector column.
- **Reader grants cover the tables that exist at apply time.**
  `postgresql_grant.reader` grants `SELECT` on existing tables in `public`
  and sets no default privileges, so a table created later is not readable by
  `ducklake_reader` until the next apply.

## Traps

- **Exporter versions.** v0.16.0 could not read PostgreSQL 17 or later and
  logged the same error 3454 times in one allocation. v0.20.1 fixes it, but
  only with `--collector.stat_checkpointer`, which ships off. The counter
  names changed too. The `###` block in `postgres.hcl` has the detail. Check
  the dashboards before the next bump.
- **The exporter is scraped twice.** Prometheus has a static `postgres` job
  on `192.168.2.30:9187`, and the sidecar's Consul service carries the
  `prometheus` tag, so the `consul_services` job scrapes it again under
  `job="postgres-exporter"`. `PostgresScrapeDown` reads
  `up{job="postgres"}`, the static job only. `PostgresDown` reads `pg_up` with
  no job selector, so it sees both scrapes and fires two series. Dropping the
  static job leaves `PostgresScrapeDown` with no data.
- **firebat is full.** Postgres reserves 2200 MHz between its two tasks, and
  with HAProxy the node is committed to about 3100 MHz. That is why the
  registry and both backup jobs run elsewhere.
- **Role memberships.** `postgresql_role` strips memberships granted by
  `postgresql_grant_role` on the next apply. See
  [Terraform write-only credential chains](/practices/terraform-write-only-credentials.md).
- **Backups need no change per database.** `pg_dumpall` copies every
  database, which is how `openviking` got covered without an edit
  (backup-swap-memex-for-openviking). See
  [GCS backups](/components/gcs-backups.md).

## Where credentials are heading

[ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md)
chose Vault's database secrets engine over PostgreSQL 18 OAuth, and
[ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md)
gives each converted job its own JWT role. Neither is rolled out: R3 is
blocked, R7 is ready, R8 is a stub. The spike's findings are in
[Short-lived Postgres credentials from Vault](/proposals/postgres-dynamic-credentials.md).
The spike's Terraform, `database-secrets-poc.tf`, was deleted from the
applications root in 19c1696. Any applications apply since then plans to
destroy whatever of it that state still tracked, so do not assume the
`database/` mount it describes is still live.

## The migrations folder

`applications/migrations/` holds a golang-migrate scaffold from 8abced4 that
nothing wires in. Its `justfile` points `migrate` at `./migrations` while the
files are in `db/migrations`, and aliases a `setup` recipe that does not exist.
The one migration creates a role `ducklake` with an empty password, which
Terraform does not declare, and its down file drops a `users` table instead.
Services own their schema (Bifrost migrates its own) and Terraform owns roles.
Treat the folder as dead until someone decides otherwise.
