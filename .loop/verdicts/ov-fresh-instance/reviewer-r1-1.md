---
type: verdict
title: 'Verdict: ov-fresh-instance reviewer round 1'
description: 'reviewer verdict for round 1 of ov-fresh-instance: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T15:08:22+00:00'
slug: ov-fresh-instance
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. It adds the new bucket, schema and volume. It moves the `openviking` key's policy off the old bucket, keeping the key's address. It keeps the old bucket's catalog entry, so Terraform does not destroy it. It adds a separate sync line and GCS prefix for the new bucket, adds the bucket to the restore allowlist, and drops veerle. I re-ran the gates and they are green. Mutating the storage catalog and the backup line makes the r2 and r3 tests fail. The cutover order in the README is safe. All three findings are about docs and none blocks: the README does not say how to collect r6/r8 evidence, the log cites the old ADR number and conflicts with main, and two comments are now false.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass, r1 to r5 pass, stamp green 6bcf7c8c12c642cb8250c87ba39fe4134a2ab5a8a2465f395e4ff287ec72936f.
- Read the whole staged diff, plus `storage.tf`, the openviking jobspec header, and the consumer resources in `identity.tf` and `secrets.tf`.
- `storage.tf`: `seaweedfs_users` is keyed by user name, so `aws_iam_user.seaweedfs["openviking"]` and its access key keep their addresses. Only the policy is replaced, because its name now ends in `-openviking-v2` (spike 4 covered this). `aws_s3_bucket.seaweedfs["openviking"]` stays in `for_each` with no attribute change. The backup and restore policies grow in place to cover both buckets. `secrets.tf` still writes `default/openviking/seaweedfs` from the same key.
- Tests checked by mutation in a scratch copy. Giving user `openviking` read on the old bucket fails `test_old_bucket_is_read_only_for_openviking`. Pointing the v2 sync at `minio/openviking/` fails `test_v2_bucket_has_its_own_backup_prefix` and the coverage test. r1, r4 and r5 assert what their `fails_when` names. r5 checks that the six step markers exist and appear in order.
- Cutover order (r6 to r8). Step 1 stops the only writer to the old bucket. Only openviking reads `default/openviking/{db,seaweedfs}`, and Hermes and leo-consumer reach the store through the API. Step 3 (infrastructure) creates `openviking_data_v2` before step 5 registers the job that mounts it. The infrastructure apply does not touch the openviking job. Step 4 creates the schema before the first boot, as spike 1 requires. In step 5 the applications apply creates the bucket, replaces the policy, then registers the job; the new `depends_on` enforces that order. The apply cannot delete or change the old bucket, because its catalog entry is kept. It cannot touch the old schema, which is not a Terraform resource. It cannot touch the old volume, which is in the other root and kept. Whether the provider sees the stopped job as gone or as changed, the apply registers it with the new spec and starts it. The `grep -v` on `\restrict`/`\unrestrict` lines is correct ERE. The README covers r7's evidence. It does not cover r6 or r8 (f1).
- Veerle's removal destroys her userpass user, entity, aliases, group membership and the `default/vault/veerle` KV metadata. That matches the variable's description: she used OpenViking and nothing else. No tfvars overrides the default.
- Merge hazards against main (the patch applied with `git apply --check` to `git archive main`). `services.tf` applies cleanly next to main's `hermes_version` bump. `.okf/decisions/index.md` and `.okf/log.md` conflict, since both sides append at the same place (f2). `summary.md` applies cleanly, but main's front matter has `checked.against` set to ADR 0020. Run `kmctl check` (and `kmctl summary ack` if it asks) after the merge. Main's changes to hermes.hcl, SOUL.md, Dockerfile and test_hermes_version.py do not overlap this branch. Main makes Hermes tools-only, which helps r6: after the restart, Hermes does not write to the new bucket on its own.

## Findings

- **f1** (docs, non-blocking): add a "Verify" step after step 6 with the r6 checks, done before anything writes: `curl /ready`, `rclone lsf -R seaweedfs:openviking-v2` with the backup key, `scripts/ov_identity_probe.py` for both tokens, a lab/jasper search, and a Hermes `viking_search`. Add the r8 check: force `backup-s3` (`docs/how-to/run-a-backup-job-on-demand.md`) and list both GCS prefixes. Also pin the Postgres image tag for the before and after dumps. pg_dump writes its own version into the dump header, so a re-pulled `postgres:18` could change the hash with no data change.
- **f2** (docs, non-blocking): when merging, keep main's ADR 0020 line and put 0021 after it in `decisions/index.md`. In `log.md`, change the two `decisions/0020-openviking-starts-over-on-a-v2-store` citations to `0021`, and merge this branch's entries under one date heading after main's.
- **f3** (docs, non-blocking): edit the `###` comment at `deployments/infrastructure/oidc.tf:140-144` so it says the 2920 objects are in the old bucket. Editing it is free: it is outside any heredoc. Also fix `.okf/components/openviking-database.md:30` so it says the old schema was the one ov.conf.json named.

## Notes

The restore user keeps `s3:*` on the old bucket. The plan accepts this, and the ADR says the old store is read-only "for OpenViking", which is accurate.
