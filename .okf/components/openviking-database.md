---
type: component
title: The OpenViking database
description: The openviking Postgres database, role, vector extension and schema tables existed before the service, so the adapter adopts them rather than migrating. Leftover dbg_fts schemas are dropped by hand, never by Terraform.
tags: [openviking, postgres, pgvector, database]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: app-database
    resource: deployments/applications/database.tf
  - id: ov-conf
    resource: deployments/applications/services/openviking/ov.conf.json
  - id: openviking-readme
    resource: deployments/applications/services/openviking/README.md
---

# The OpenViking database

The service that uses this database is
[the OpenViking service](/components/openviking-service.md), and the server it
runs on is [Postgres](/components/postgres.md).

## The database already existed

The `openviking` database, its role and the `vector` extension were created
before this service was: `623abf8` added them to `local.roles` and
`local.databases` in `deployments/applications/database.tf` a week before OV1
added the job. The `openviking` schema that `ov.conf.json` named until the
v2 store (it now names `openviking_v2`, ADR 0021) is not a Terraform
resource. It already held empty
`ov_collections` and `ov_indexes` tables matching ov-postgres v0.2.0's DDL, so
the adapter adopts them rather than migrating.

Five `dbg_fts*` schemas from earlier experimentation are still there. Dropping
them is a hand-run operator step on purpose: a `postgresql_schema` resource
would put a live `DROP` behind every future apply against the vector store's
own database.

## Schema openviking_v2

Since `ov-fresh-instance` (2026-10-20) `ov.conf.json` and
`OV_REFLECT_DELTAS_SCHEMA` name schema `openviking_v2` in the same database.
The `openviking` schema stays, untouched, as the backup of the old store
([ADR 0021](/decisions/0021-openviking-starts-over-on-a-v2-store.md)).

`openviking_v2` is not a Terraform resource either. The operator creates it
as the `openviking` role, with `CREATE SCHEMA IF NOT EXISTS openviking_v2`,
before OpenViking first boots on it. The adapter would create it, but ov-ext
opens its delta store in `install()`, before the adapter runs, so on an absent
schema change capture stays off until a restart (spike:ov-fresh-instance/1).
The same spike showed a second schema in one database leaves the first one's
tuple counters and dump hash unchanged and adds nothing to `public`.
