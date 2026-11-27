---
type: verdict
title: 'Verdict: ovsq-keyless-local-sync plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ovsq-keyless-local-sync: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-27T19:07:47+00:00'
slug: ovsq-keyless-local-sync
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan holds up apart from one wrong premise. The single listed risk, a
`StringEquals` on a missing claim counting as a match, is settled by
spike:ovsq-keyless-local-sync/1. But the plan treats the identity token's ttl
as the lifetime of the S3 credentials, and in SeaweedFS 4.48 it is not: the
printed credentials would last one hour unless the command requests
DurationSeconds=900. That is a cheap revision, not a rethink, so the verdict
is fail, not reject.

## Checked

- Spike 1: README outcome, stdout (16 of 16 required checks passed, with
  controls), run.json (exit 0). It answers the listed risk. A token without
  the claim is refused by each role, a wrong `sub` is refused, and the
  Get/Put/Delete policy stays inside `ov-sync/JasperHG90/local/`, with
  `JasperHG90/localx/` denied.
- Anchors exist and behave as described: `vault_identity_oidc_role.ci_ov_sync`
  and key `identity_tokens` (allowed_client_ids includes `seaweedfs`) in
  oidc.tf. `vault_identity_entity.operator` and the `openviking_user`
  policy/group pattern are in identity.tf. `local.seaweedfs_iam` with the
  `vault` provider and the `ci-*` StringEquals trust are in
  infrastructure/services.tf. `vault.read_creds` is in auth/vault.py.
  `LAZY_SUBCOMMANDS` with `env` is in main.py. `cli/tests/fixtures/seaweedfs_iam.py`
  and `cli/tests/test_seaweedfs_iam_config.py` both exist.
- `Mapping.Resolve` and `LoadMapping` in mapping.go: an exact two-segment
  prefix, `_state/` skipped, the rest appended to the root, so
  `JasperHG90/local/projects/notes/x.md` lands at
  `viking://user/jasper/resources/local/projects/notes/x.md`.
- ovsq upstream (openviking_extensions origin/main, packages/ov-sync-queue):
  s3store.go uses `credentials.EnvAWS` first. config.go requires a two-part
  prefix, refuses a subdir under `_state`, and keys the manifest as
  `<prefix>/_state/ovsq-<source>.json`, so folders that share the prefix but
  have different `source` values do not delete each other's keys. That holds
  as long as each folder keeps its own `source`, which the plan says.
- Missing manifest without List: `Store.Get` maps only `NoSuchKey` to
  not-found. spike:ci-openviking-sync/1 recorded that SeaweedFS returns
  NoSuchKey, not AccessDenied, for a missing key under the same no-List
  policy, so ovsq's first run works.
- The CLI logs in through userpass to `vault_identity_entity.operator`, so a
  token it mints carries the operator entity id as `sub`. The entity is in the
  same Terraform root as the SeaweedFS trust policy that pins it.
- SeaweedFS 4.48 source (`~/.cache/spike-src/seaweedfs`, tag 4.48):
  `CalculateSessionDuration` and the 900-second minimum in s3api_sts.go.
- Facts against prose: the five outcomes match the bullets in the intent. Only
  O4 is a behaviour, and it can ship alone once its needs are in. O4 needs O3
  only for its live check, which its checked_by includes. Each fixes and goal
  reads correctly.

## Findings

- p1: STS credential lifetime. SeaweedFS ignores the web identity token's exp
  when it sets the session length, and the configured default is 1h. The plan
  never says the command sends DurationSeconds=900, so "15-minute
  credentials" is false as written, and the faked-STS test cannot show it.

## Notes

- O5's touches do not list the new decision record under `.okf/decisions/`,
  which the prose names. Its filename is not known before `kmctl new
  decision` runs, and nothing else touches that folder, so this does not
  change how plan.split decides. It is not a finding.
- Credentials that last 15 minutes can expire during a large first sync. ovsq
  writes its manifest after each batch of 100, so rerunning
  `eval "$(localstack ov-sync-env)"` and `ovsq run` resumes. The how-to should
  say so. That is a docs detail, not a risk to the plan.
