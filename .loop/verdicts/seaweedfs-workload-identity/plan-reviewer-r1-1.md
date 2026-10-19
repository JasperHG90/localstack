---
type: verdict
title: 'Verdict: seaweedfs-workload-identity plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-workload-identity: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:52:28+00:00'
slug: seaweedfs-workload-identity
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach holds. Spikes 1 to 4 settle the three listed risks: JWKS
discovery, per-job binding through trust-policy conditions on nomad_job_id
and sub, and the client changes (RoleArn and RoleSessionName). The plan can
still break in three ways it does not cover. It does not say how the IAM
config reaches SeaweedFS (p1). That config has not been run beside the admin
and API-made users that earlier tickets put on the same server (p2). Its
outcome test would replace the live tempo job (p3). Each needs a revision,
not a rethink. Verdict: fail.

## Checked

- The plan and its eval. The eval has no rows.
- The README, run.json and config files of spikes 1 to 4. Spike 2 checks 17
  of 17 binding cases with the policyClaim comma hole. Spike 4 shows both
  clients working with per-job roles. All four ran only with
  -s3.iam.config, with buckets made by weed shell, no -s3.config admin and
  no -s3.iam.readOnly=false (spike 4 files/iam.json and spike.sh line 15,
  spike 2 start_swfs).
- The sibling plans seaweedfs-service, seaweedfs-buckets and
  seaweedfs-cutover, and the flags their spikes ran with. Service and
  buckets used -s3.config with -s3.iam.readOnly=false and never
  -s3.iam.config. Buckets spike 1 logged "no signing key found for STS
  service".
- deployments/applications/services/tempo.hcl (job "tempo", namespace
  default) and nomad_job.tempo in deployments/applications/services.tf.

## Findings

- p1: no stated home or delivery path for provider, roles, trust policies,
  signing key and defaultEffect. The only proven path is a config file in
  the infrastructure root's seaweedfs job, which this plan does not scope.
- p2: no spike covers the IAM config file next to the static admin and
  API-made users, so it could break seaweedfs-buckets' identities. This
  needs a spike.
- p3: a throwaway job named tempo in the default namespace replaces the
  production tempo job.

## Notes

Not a split signal. Once p1 settles the route, the work is one config
change, one secret and two docs. The cutover ticket must keep the trap from
spike 3: minio-go without AWS_ROLE_ARN silently falls back to anonymous
credentials. tempo.hcl has a comment saying AWS_ROLE_ARN is deliberately
absent, and the cutover has to reverse that.
