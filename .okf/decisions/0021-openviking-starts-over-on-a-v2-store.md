---
type: decision
title: "ADR 0021: OpenViking starts over on a v2 store"
description: "OpenViking moves to a new bucket, schema and workspace volume with one lab/jasper identity, and the old store stays as a read-only backup because its key is moved off it."
tags: [adr, decision, openviking, seaweedfs, postgres]
generated:
  by: process:kmctl/0.12.1
  at: 2026-10-20T14:42:29Z
status: stable
sources:
  - resource: "deployments/applications/storage.tf"
  - resource: "deployments/applications/services/openviking/ov.conf.json"
  - resource: "deployments/applications/services/openviking.hcl"
---

# ADR 0021: OpenViking starts over on a v2 store

## Context

OpenViking held its blobs in SeaweedFS bucket `openviking`, its vectors in
schema `openviking` of database `openviking`, and its queue and scratch in host
volume `openviking_data`. The bucket carried account `lab` plus per-person
accounts `jasper` and `veerle`, and users `jasper`, `hermes`, `veerle` and
`default`, left over from before the OIDC flip. The operator, Hermes,
leo-consumer and ov-ext reflection all resolve to `lab`/`jasper` already, and
veerle was the only caller outside it. The operator chose to start over with
one account and one user, and to keep the old data until they say delete.

## Decision

OpenViking runs on bucket `openviking-v2`, schema `openviking_v2` and volume
`openviking_data_v2`, all new. The `openviking` storage user's policy moves to
`openviking-v2`, so the key in `default/openviking/seaweedfs` keeps its id and
secret and loses all access to `openviking` (spike:ov-fresh-instance/4). The
old bucket keeps its catalog entry with no writers, and both buckets stay in
`local.seaweedfs_durable_buckets`, so the backup key reads both and the
restore key writes both. `backup-s3` syncs `openviking-v2` to its own GCS
prefix, `minio/openviking-v2/`. veerle's entry leaves
`var.vault_openviking_consumers`.

No account is created. Under `auth_mode: oidc` a `lab`/`jasper` token works on
an empty bucket with no Admin API call (spike:ov-fresh-instance/3). The schema
is created by hand before the first boot, because ov-ext opens its delta
store before the adapter creates the schema (spike:ov-fresh-instance/1).
`deployments/applications/services/openviking/README.md` has the cutover
order.

Rejected: emptying the existing bucket, schema and volume in place. That
needs no new names, but it destroys the only copy apart from the nightly GCS
backup, and the next `backup-s3` run would then delete that copy too, since
`rclone sync` deletes at the destination. Also rejected: keeping the key's
access to the old bucket and relying on the config to name only the new one.
That keeps the old store read-only by convention, and one wrong bucket name
in `ov.conf.json` would write into the backup.

## Consequences

- The old bucket, schema and volume cost storage until the operator deletes
  them. Deleting them is a separate change.
- The old store is read-only in fact for OpenViking: its key is denied put,
  get, list and delete on `openviking`.
- The nightly backup copies both buckets, and fails between the
  infrastructure and applications applies of the cutover, because the new
  bucket does not exist yet.
- veerle has no OpenViking login. The per-person API keys under
  `default/openviking-users/` still name `jasper` and `veerle`. Nothing reads
  them under OIDC, and this change leaves them alone.
