---
type: verdict
title: 'Verdict: seaweedfs-cutover-registry reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-cutover-registry: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T08:04:02+00:00'
slug: seaweedfs-cutover-registry
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The registry now logs in to SeaweedFS keylessly through its own role, and the
live cutover evidence covers every part of r2. The marker cleanup was guarded
and checked against MinIO, and leaving the HAProxy jobspec comment stale
follows the repo's rule and is recorded in the component page. Pass.

## Checked

- Gates, re-run from the worktree with `loopctl gate stamp`: pre_commit pass,
  cli_tests pass, eval-row r1 pass, stamp green
  dabdea1236a1806a20377a424e310cac3dbc685b83b388b978326a3795c67e6b.
- Code: registry.hcl identity is `seaweedfs` with audience `seaweedfs` and JWT
  at secrets/nomad_seaweedfs.jwt. The helper POSTs to s3_host:8333 with
  RoleArn=arn:aws:iam::role/registry and RoleSessionName=registry.
  regionendpoint is `http://s3_host:8333`. services.tf passes s3_host from
  data.consul_service.seaweedfs, which exists in the root. The registry role
  already exists in local.seaweedfs_keyless_jobs (infrastructure root) and
  grants s3:* on the bucket. That covers the actions spike 1 named. Dropping
  depends_on on minio_iam_policy.registry_wi is right because nothing in this
  root gates the role now. The policy, the Vault KV entry and the static keys
  stay as rollback paths, as the comments say. Escaping (`$${jwt}`) still
  matches the double-template rule.
- r1: tests/test_registry_s3.py asserts each part of fails_when. It checks the
  audience `seaweedfs` inside the identity block, RoleArn and RoleSessionName
  inside the STS URL, that 192.168.2.29:9000 is absent, and that
  regionendpoint uses s3_host fed by the Consul lookup. Reverting any of these
  fails a test.
- r2 (judgment): read spike 2's README, stdout.txt, run.json (exit 0) and the
  scripts. backup-minio alloc e12ec616 and restore-s3 alloc 72fa47f2 both
  exited 0. restore-s3 runs rclone check, so a 0 exit means the check passed.
  snapshot.py compared all 33 tags by tag and digest, plus config hashes and
  192 layer digests and sizes, against a baseline taken on MinIO before the
  switch. Layers went through the presigned SeaweedFS redirect. The result was
  identical. push_check.py pushed a new OCI image (201) and read it back by
  tag and digest (200), and the layer bytes matched. SeaweedFS went from 399
  to 404 objects and MinIO stayed at 399. That meets the outcome.
- Marker deletion (drop_markers.py): it refuses if MinIO has any key ending
  in `/`, and it deletes only zero-byte `/` keys in SeaweedFS. It then requires
  SeaweedFS's full key-to-size map to equal MinIO's, and MinIO was frozen
  because the registry was stopped. The 725 matches the count predicted in
  spike:backup-durable-buckets/3. The equality check after the delete also
  rules out SeaweedFS having deleted directory contents along with a marker.
  This is sound, and gcs-backups.md records that a future registry restore
  needs the same step.
- HAProxy step 3: the edge path did not change. Only the backend behind the
  registry moved. The comment that still says MinIO sits inside a jobspec, so
  editing it would re-register HAProxy. .claude/rules/terraform-file-layout.md
  says a stale reference there stays stale, and container-registry.md says so
  next to the timeout trap. Acceptable.
- Docs: read the diff of every changed docs/ and .okf page. Checked the claims
  that MinIO has no keyless job and only backup-minio reads it (memex.hcl is
  commented out), that 8333 is open to 192.168.0.0/16
  (infrastructure/services.tf:360), and that default/registry/seaweedfs exists
  (applications/secrets.tf:476). The frozen-backup gap is stated in the
  reference page, gcs-backups.md, minio.md and container-registry.md.

## Findings

None.

## Notes

- The check image's five objects (repo seaweedfs-cutover-check, manifest
  deleted) stay in SeaweedFS until someone runs registry garbage-collect. They
  do no harm.
- push_check.py pushed small blobs with a single PUT, so this run did not
  exercise chunked or multipart pushes on the production job. Spike 1 covered
  them with the same registry version and role credentials, so I accept it.
