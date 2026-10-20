---
type: verdict
title: 'Verdict: ov-fresh-instance plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-fresh-instance: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T14:31:14+00:00'
slug: ov-fresh-instance
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Both listed risks are settled by their spikes. The approach works: a fresh
bucket, schema and volume, with no account bootstrap under OIDC and the schema
created before first boot. Two things could still break it. The IAM policy move
that is meant to make the old bucket read-only in fact has never been run on
SeaweedFS, and its delete-then-put replace may remove the key or leave its old
grant in place (p1, needs a spike). The old-store baseline is taken while the
old instance can still write, so the Outcome's exact match can fail with no
leak (p2). Neither forces a rethink, so the verdict is fail, not reject.

## Checked

- Spike 1 (exit 0): the outcome, plus the PASS lines in stdout for the created
  schema, the unchanged counters and dump hash, and nothing new in `public`.
  It also shows the delta store failing to open on first boot, which the plan
  handles by creating `openviking_v2` beforehand. Risk 2 is answered.
- Spikes 2 (exit 1) and 3 (exit 0): spike 2 failed only on the earlier "only
  lab/jasper" outcome, because of the preset `default` tree. Spike 3's key
  listing matches the revised Outcome: 6 keys under `lab/`, 25 preset keys, no
  `_system/`. Risk 1 is answered. The limits (stub models, fake issuer, admin
  S3 key) do not touch the question.
- `storage.tf`: users are keyed by user name, so the user and key keep their
  addresses. The policy name is `${each.key}-${each.value.bucket}`, so it is
  replaced (p1). `seaweedfs_credentials` is keyed by user, so the Vault path
  stays as the plan says.
- `openviking.hcl` and `ov.conf.json`: the bucket, schema,
  `OV_REFLECT_DELTAS_SCHEMA` and volume `source` are the only places the store
  is named. No other job uses the openviking DSN or bucket. backup-postgres
  only reads.
- Infrastructure `services.tf`: the `openviking_data` volume uses the `mkdir`
  plugin pinned to radxa, so a v2 copy is a plain add.
- Removing veerle: every consumer resource is driven by the map. The jwt-lab
  alias precondition still holds with an empty map, and `vault_identity_group`
  can take an empty member list.
- `backup-s3.hcl` and `restore-s3.hcl`: one sync line and one `case`, as the
  plan says.

## Findings

- p1: the policy move from `openviking` to `openviking-v2` is a
  delete-then-put replace on SeaweedFS IAM that no spike has run. It may delete
  the identity and its key, or keep the old bucket grant, which breaks either
  the cutover or the read-only guarantee. Hand it to spike-runner with the
  question written in the finding.
- p2: the baseline is taken before the old job stops, so the Outcome's
  exact-match check can fail on a normal last write from the old instance.

## Notes

The ticket's scope is fine and does not need splitting. The eval has no rows
yet. That is not a plan risk, but the Outcome has many separate checks that
will need rows.
