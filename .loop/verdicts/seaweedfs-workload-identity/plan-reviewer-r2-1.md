---
type: verdict
title: 'Verdict: seaweedfs-workload-identity plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of seaweedfs-workload-identity: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:01:16+00:00'
slug: seaweedfs-workload-identity
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

All three round 1 findings are resolved. The config route is named and
matches what the spikes ran. Spike 5 covers the combined server. The outcome
test no longer touches tempo. I found no new risk that could break the
plan. The questions left (probe bucket handling, the signing key encoding,
whether removing a role from the file revokes it, registry's actions) are
answered faster by building. Verdict: pass.

## Checked

- The revised plan, and the eval, which still has no rows.
- Spike 5: README, run.json (exit 0), stdout (33 PASS lines across the
  first-tf and restart phases, clean second and post-restart plans),
  files/iam.json and files/spike.sh. Its flags match the seaweedfs-service
  jobspec in the worktree (-s3.config, -s3.iam.readOnly=false, -ip.bind,
  -volume.max=0, volumeSizeLimitMB=1024, iceberg/lance off, master.toml
  copy_1=2), with -s3.iam.config added. The role is bound on nomad_job_id
  and sub, as in spike 2.
- Spike 1 again, for discovery. It ran from the devcontainer, not
  orangepi4a, and relies on MinIO on the same node reaching the same URL
  today. That is acceptable.
- The worktree jobspec deployments/infrastructure/services/seaweedfs.hcl and
  services.tf/secrets.tf. The job already has `vault {}` and reads
  default/seaweedfs/admin, so a sibling path default/seaweedfs/sts follows
  the same access pattern. nomad_job.seaweedfs already passes template
  variables, so adding the job list and the key path fits that shape.
- Registry and the role policy. The planned role grants s3:* on
  arn:aws:s3:::BUCKET and BUCKET/*, which covers every bucket-scoped call
  the distribution S3 driver makes: list, multipart, copy and delete.
  Registry does not call ListAllMyBuckets. If the separate registry push
  spike finds one more action, that is a line in the job list local, not a
  change of approach. That is no reason to hold this plan.
- The weed 4.48 binary (strings). It has both memory and filer role and
  policy stores (integration.FilerRoleStore, policy.FilerPolicyStore).

## Findings

None. p1, p2 and p3 are resolved, as recorded in the front matter.

## Notes

These are for the builder. None of them breaks the plan.

- Probe bucket. The plan does not say who creates `wi-probe`. Creating and
  deleting it by hand with the admin key (aws s3 mb / rb, path-style, as
  spike 5 did) leaves no Terraform state in either root. Do not add it to
  the applications root's bucket list, because then removing it would take
  a second applications change. Removing the probe role means a second
  infra apply, and the re-rendered template restarts SeaweedFS. Plan for
  that brief outage.
- Role removal. Weed 4.48 has filer-backed role and policy stores as well
  as memory ones, and the spikes never set storeType. Once the probe role
  is gone from the file, check that a wi-probe token gets 403. That proves
  the file is still the source of truth and that a role cannot survive in
  the filer. If it does survive, set the stores to memory explicitly.
- Signing key. SeaweedFS decodes `sts.signingKey` as base64, so spike 5
  passed a base64 string. A raw random_password must be base64-encoded in
  the template, or generated so that it decodes to a key long enough for
  SeaweedFS. Startup shows this at once.
- The cutover still carries spike 3's trap: minio-go without AWS_ROLE_ARN
  falls back to anonymous credentials without an error.
