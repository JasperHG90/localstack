---
type: verdict
title: 'Verdict: seaweedfs-workload-identity reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-workload-identity: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T06:33:05+00:00'
slug: seaweedfs-workload-identity
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. The infrastructure root writes an STS signing key to default/seaweedfs/sts. The seaweedfs job renders secrets/iam.json from local.seaweedfs_iam plus that key, and passes it with -s3.iam.config. The config has defaultEffect Deny, one provider (Nomad's issuer, clientId seaweedfs, no policyClaim), and one role and policy per keyless job. Each role's trust policy pins nomad_job_id and sub, and each policy reaches only that job's bucket. The live evidence holds up and the probes are gone. Two findings, neither blocking. The r1 test does not check the Terraform wiring it claims to cover. The audience registry in the explanation doc misses the new audience.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests, pass eval-row r1, "stamp green: 1e4cd7551b960a7bc216b205f111cd2ddcf227a075b29537ea63704106e5adc3".
- I read the full diff of secrets.tf, services.tf, services/seaweedfs.hcl and the new test. Rendering: valid JSON never contains `{{`, so the consul-template body cannot be misparsed. The JSON has no `${` that Nomad's HCL parse would interpolate. The `}` that closes the object sits before `{{ end }}` as plain text. The default template change_mode restarts the task, which matches the docs' line that a new job needs a restart. The s3:* bucket-scoped policy matches MinIO's tempo_wi/loki_wi.
- r1: I ran mutations on a scratch copy. defaultEffect Allow fails the test, as it should. A wrong Vault path and an empty iam_members both pass (f1).
- r2 (judgment): spike 6. The admin key reads back `from-wi-probe` = "written by wi-probe", which only an STS-issued credential for the probe role could have written. The static loki key writes its own bucket and gets AccessDenied on tempo. The applications-root plan reports "No changes" with the IAM config loaded. The wi-probe-other refusal rests on alloc exit code 0 in a script that exits 0 only on HTTP 403. That is weaker evidence, but it agrees with spikes 2 and 4 on the same trust-policy shape. I accept it.
- r3 (judgment): I ran `nomad job status` myself: wi-probe and wi-probe-other both return 404, and seaweedfs is running (submitted 08:26 +02:00, after cleanup). The tree's job list has no wi-probe. Spike 7 shows the six buckets and no wi-probe bucket, and STS still refuses a junk token.
- r4 (judgment): workload-identity-chain.md describes the per-job role binding (nomad_job_id and sub, RoleArn and session name) and the EdDSA trap. ADR 0017 rejects claim mode, citing the policyClaim comma split (evil,tempo) and the issuer/audience-only trust policy. Both are present.
- Consistency: seaweedfs.md and ADR 0017 match the code. The explanation doc's audience registry does not (f2).

## Findings

- f1 (test-strength, non-blocking): test_seaweedfs_iam_config.py hard-codes `sts_secret = "secret/data/default/seaweedfs/sts"` and its own `iam_members` expression in the console call, so the "comes from Vault at default/seaweedfs/sts" assertion only checks the test's own input. Fix: assert `vault_kv_secret_v2.seaweedfs_sts` has `name = "default/seaweedfs/sts"` and that nomad_job.seaweedfs passes `sts_secret = vault_kv_secret_v2.seaweedfs_sts.path`. Better, take the templatefile arguments from services.tf so the test cannot drift from the real call.
- f2 (docs, non-blocking): add a `seaweedfs` row to the audience registry in docs/explanation/workload-identity.md (SeaweedFS STS, deployments/infrastructure/services.tf). If it shares a verifier class with minio during the cutover, say so in a sentence.

## Notes

The deny evidence in spike 6 exists only as an alloc exit code described in prose, because the alloc is purged. Future probes could print the exit code into stdout.txt via `nomad alloc status` before the purge.
