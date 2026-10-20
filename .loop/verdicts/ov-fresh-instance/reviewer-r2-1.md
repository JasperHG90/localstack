---
type: verdict
title: 'Verdict: ov-fresh-instance reviewer round 2'
description: 'reviewer verdict for round 2 of ov-fresh-instance: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T15:18:15+00:00'
slug: ov-fresh-instance
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

All three round-1 findings are fixed. The README cutover now has steps 7 to 9 for the r6 and r8 evidence and pins `postgres:18.0`. The log cites ADR 0021. The oidc.tf comment and the database component note are true again. One new non-blocking docs finding: step 9 now points at a GCS listing whose comment still names four bucket folders, without `openviking-v2/`.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass, r1 to r5 pass, stamp green 69c908fc472692ef29ccde9bd6c72b31e319a174560850422d25026a30cc410f.
- Read the staged diff of the README, oidc.tf, openviking-database.md, log.md, decisions/index.md and run-a-backup-job-on-demand.md.
- Step 7: `scripts/ov_identity_probe.py` takes `--account` and `--user`, and `docs/how-to/verify-an-openviking-deployment.md` exists and runs the probe the same way. Step 8 repeats step 2 and diffs. Step 9 forces `backup-s3`. Step 2 pins `postgres:18.0` and says why.
- oidc.tf: the edit is in `###` comments outside any heredoc, so it costs no apply.
- log.md: no `0020-openviking` citation is left in the branch (grep). The branch adds one heading, `## 2026-10-20 (ov-fresh-instance)`. Main's log and decisions index still append at the same spot, because the worktree sits at 566ab44, behind main. Merging still means resolving those by hand: keep main's 0020 line first, and put this branch's entries under main's 2026-10-20 heading. The citation and ordering the round-1 finding asked for are now in place.

## Findings

- **f1** resolved: README steps 7 to 9 and the `postgres:18.0` pin, at deployments/applications/services/openviking/README.md.
- **f2** resolved: log.md cites `decisions/0021-...` and explains why 0021 was chosen. The textual merge conflict with main stays, and gets resolved at merge as noted above.
- **f3** resolved: oidc.tf:140-143 now says `lab` is the one account on the v2 store and puts the 2920-object history on the old store. openviking-database.md says `ov.conf.json` named `openviking` until the v2 store.
- **f4** (docs, non-blocking): `docs/how-to/run-a-backup-job-on-demand.md:61` has `# openviking/ registry/ models/ datalake/`, and step 9 relies on that listing to show both prefixes. Add `openviking-v2/` to the comment. That line already holds the `minio/` prefix in a doc, so test_no_minio does not stop the edit.
