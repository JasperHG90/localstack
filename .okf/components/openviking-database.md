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
---

# The OpenViking database

The service that uses this database is
[the OpenViking service](/components/openviking-service.md), and the server it
runs on is [Postgres](/components/postgres.md).

## The database already existed

The `openviking` database, its role and the `vector` extension were created
before this service was: `623abf8` added them to `local.roles` and
`local.databases` in `deployments/applications/database.tf` a week before OV1
added the job. The `openviking` schema that `ov.conf.json` names is not a
Terraform resource. It already held empty
`ov_collections` and `ov_indexes` tables matching ov-postgres v0.2.0's DDL, so
the adapter adopts them rather than migrating.

Five `dbg_fts*` schemas from earlier experimentation are still there. Dropping
them is a hand-run operator step on purpose: a `postgresql_schema` resource
would put a live `DROP` behind every future apply against the vector store's
own database.
