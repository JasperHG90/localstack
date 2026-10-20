---
type: verdict
title: 'Verdict: bifrost-update reviewer round 2'
description: 'reviewer verdict for round 2 of bifrost-update: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T10:35:49+00:00'
slug: bifrost-update
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 is fixed. The pre-apply dump now sits under its own name in GCS. Its size,
MD5 and CRC32C match the 10:24:51 UTC original. The component page names the
object, says it is a whole-cluster dump to restore only `bifrost` from, and
gives the correct delete date. The fix broke nothing, and the stamp is green
on this tree.

## Checked

- Gates: `loopctl gate stamp` from the worktree passed pre_commit, cli_tests
  and eval-row r1, with "stamp green: 7866ba40...". That matches the
  fingerprint bound to this round's placeholder.
- The object, listed read-only with the backup service account key from
  Vault: gs://localstack-cluster-backups/postgres-pre-upgrade/bifrost-2.0.0-pgdumpall-2026-10-20.sql.gz
  has Content-Length 1399446141, MD5 uTfank6V9fcIQGtAWWsA6w== and CRC32C
  dHwmRg==, the same as postgres/pgdumpall-2026-10-20.sql.gz, which was
  created at 10:24:51 UTC. The copy was created at 10:32:20 UTC.
- Delete date: deployments/infrastructure/storage.tf has one bucket-wide
  lifecycle rule (age 180, Delete) with no prefix condition. Age counts from
  the copy's own creation on 2026-10-20, and 2026-10-20 plus 180 days is
  2027-04-18, so the page is right. I could not read the live bucket's config,
  because the service account lacks storage.buckets.get. The Terraform
  resource and docs/reference/gcs-backups.md agree on the rule.
- "A name no job writes": backup-postgres runs `rclone copy` into
  `postgres/` only. backup-s3 runs `rclone sync` into `minio/<bucket>/`
  prefixes only, so no sync can delete objects under `postgres-pre-upgrade/`.
  Nothing else in deployments/ writes to the bucket.
- The diff of .okf/components/bifrost.md against main: the new paragraph is
  correct, and the rest of the version-history paragraph matches round 1.

## Findings

- f1: resolved. .okf/components/bifrost.md:149-158 names the copied object,
  says it is a whole-cluster dump to restore only `bifrost` from, and gives
  the 2027-04-18 delete date. The object exists and matches the original.

## Notes

- The 180-day rule will delete the copy on 2027-04-18. If 2.0.0 might still
  be needed after that date, someone has to move the copy somewhere else.
