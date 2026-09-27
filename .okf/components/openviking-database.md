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
  - id: openviking
    resource: git:3ec5d1e:docs/openviking.md
    last_modified: 2026-09-12
---

# The OpenViking database

The service that uses this database is described in
`docs/reference/openviking.md`.

## The database already existed

The `openviking` database, its role and the `vector` extension were created
before this service was. Its `openviking` schema already held empty
`ov_collections` and `ov_indexes` tables matching ov-postgres v0.2.0's DDL, so
the adapter adopts them rather than migrating.

Five `dbg_fts*` schemas from earlier experimentation are still there. Dropping
them is a hand-run operator step on purpose: a `postgresql_schema` resource
would put a live `DROP` behind every future apply against the vector store's
own database.
