---
type: verdict
title: 'Verdict: ovsq-keyless-local-sync reviewer round 1'
description: 'reviewer verdict for round 1 of ovsq-keyless-local-sync: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T20:51:26+00:00'
slug: ovsq-keyless-local-sync
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. Vault gets the `local-ov-sync` token role,
an operator-only policy and group, and SeaweedFS gets a role that pins both the
`local_ov_sync` claim and the operator's `sub`, with Get/Put/Delete on
`ov-sync/JasperHG90/local/*` only. The consumer has the prefix, and
`localstack token s3 ROLE` sends `DurationSeconds=900` and keeps the
empty-stdout-on-failure rule. Every gate passes when I run it myself. Two
findings, neither blocking: a stale line in the CLI docs and one gap in a test.

## Checked

- Gates, run myself from the worktree (`loopctl gate stamp` was denied by the
  sandbox, so I ran what it runs): `just pre_commit` passed every hook,
  including terraform fmt/validate, ruff, mypy strict and the ov-sync-consumer
  go tests. `uv run --directory cli pytest -q` gave 851 passed, 21 deselected.
  `kmctl check` printed "all checks passed".
- r1: `test_local_ov_sync.py -k vault` (3 passed). Asserts name, client_id
  through `local.seaweedfs_audience`, ttl 900, the literal template, a single
  policy path with `read` only, and a group whose only member is
  `vault_identity_entity.operator.id`. Each fails_when clause is covered.
- r2: `test_seaweedfs_iam_config.py -k local_ov_sync` (3 passed). Renders the
  real config with terraform console and checks the whole Condition dict with
  both StringEquals keys, the exact policy Statement, and that no `ci-*` role
  mentions `local_ov_sync`. The ci-role filter in
  `test_openviking_sync_action.py` changed from "not Federated nomad" to
  "name starts with ci-". That is needed now that a non-CI vault role exists,
  and the local role has its own test.
- r3: `-k prefix` (2 passed). Covers the entry and nesting between mapped
  folders. See f2 for the gap.
- r4: `-k success` (3 passed). Checks stdout exactly, the session token used
  to mint, `RoleArn`, `WebIdentityToken` and `DurationSeconds=900`, and an
  arbitrary role name.
- r5: `-k refus` (3 passed). Covers a Vault 403 (and that STS is never
  called), an STS 403, and a missing role. Each asserts empty stdout and a
  non-zero exit.
- r6: the page exists, the skeleton test passes (66) and `kmctl check`
  passes. I checked the how-to's ovsq claims (init/status/run/`--delete`,
  the `target.prefix|subdir|source` keys, `N failed` summary, BatchSize 100
  checkpoint, the `_state/ovsq-<source>.json` manifest) against ovsq's source
  and reference in the sibling openviking_extensions worktree. They match.
- r7 (judgment): I accept the implementer's live evidence. An expiry 15
  minutes after minting matches the 900 s request. The write under
  `JasperHG90/local/projects/live-check/` showed up at the mapped viking path.
  The put under `JasperHG90/localstack/` was refused. mc in place of ovsq is a
  fair stand-in, since both read the same AWS_* env chain through minio-go,
  and the subdir differs from `projects/notes` only by name. I did not repeat
  the live run.
- r8: covered by the gate runs above.
- Code: `sts.py` handles HTTPError, OSError, a body that is not XML and
  missing fields, and turns each into StsError, which becomes `fail()`.
  Values are shlex-quoted. The import adds only stdlib modules and the
  already-imported `auth.vault` to the shim path, so the lazy-import rule
  holds. The fixture swaps in the operator entity id only inside the
  seaweedfs locals block.
- Consistency: the ADR, the workload-identity explanation, the
  deployment-layers rows and the summary match the code. Dropping "neither yet
  deployed" from the summary fits the live evidence that the consumer
  processed an object.

## Findings

- f1 (docs, non-blocking): `.okf/components/localstack-cli.md` ends its shim
  section with "stdout is the token and one newline", and
  `docs/reference/cli-login.md`'s "`token` is for scripts" section describes
  only the single-token form. The `token.py` module docstring now records the
  s3 exception, but these two pages do not, and the reference has no entry for
  `token s3 ROLE` or `--endpoint`. Add one sentence and a short entry.
- f2 (test-strength, non-blocking):
  `test_no_consumer_prefix_folder_contains_another_or_the_hermes_root` checks
  `HERMES_ROOT not in roots` and nesting among mapped roots, but a mapping to
  an ancestor of the hermes root (for example `viking://user/jasper/`) would
  pass. Assert that no root is a prefix of `HERMES_ROOT`.
