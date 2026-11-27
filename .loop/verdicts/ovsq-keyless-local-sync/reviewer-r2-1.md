---
type: verdict
title: 'Verdict: ovsq-keyless-local-sync reviewer round 2'
description: 'reviewer verdict for round 2 of ovsq-keyless-local-sync: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T20:58:24+00:00'
slug: ovsq-keyless-local-sync
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Narrow round. The f1 fix is accurate: every claim the docs now make about
`localstack token s3 ROLE` matches `commands/token.py` and `auth/sts.py`.
f2 is fixed too. The gates are green when I stamp them myself. Pass.

## Checked

- `loopctl gate stamp` from the worktree: pass on pre_commit, cli_tests and
  eval rows r1 to r6 and r8. Stamp green
  523907948ed351f1e04f640fd7fe524b144f0bacefa9e392438f52cfb060e19f.
- docs/reference/cli-login.md, "`token` is for scripts": the `eval` usage
  matches the token.py docstring. The Vault path `identity/oidc/token/ROLE`
  and the session's Vault token match `sts.s3_credentials`. The RoleArn
  `arn:aws:iam::role/ROLE` matches `_assume_role`. The three export names
  match `S3Credentials.exports`, and `shlex.quote` makes them safe to `eval`.
  The 15 minutes match `DURATION_SECONDS = 900`. "stderr says when they
  expire" matches the `print(..., file=sys.stderr)`. The `--endpoint` default
  matches `sts.DEFAULT_ENDPOINT`. "A failure, or no role, exits non-zero with
  empty stdout" holds: a missing role, `StsError` and session errors all go
  through `_common.fail`, which writes to stderr and returns `typer.Exit(1)`,
  and stdout gets written only after the credentials are in hand. The
  front-matter sources now list `auth/sts.py`.
- .okf/components/localstack-cli.md: the added sentence (three `export`
  lines, no shim calls it, the empty-stdout rule still holds) is correct.
- f2: `test_no_consumer_prefix_folder_contains_another_or_the_hermes_root`
  now asserts that no mapped prefix is a prefix of `HERMES_ROOT`, so it
  fails on the root or anything above it.

## Findings

- f1: resolved in docs/reference/cli-login.md ("`token` is for scripts") and
  .okf/components/localstack-cli.md (Shims section), as above.
- f2: resolved in cli/tests/test_local_ov_sync.py:66-69.

## Notes

The `description` front matter of .okf/components/localstack-cli.md still
says "stdout of `token` is the token alone". That is about the shim
contract and is no less true than before, so I do not raise it. It could
say "for the shimmed services" in a later edit.
