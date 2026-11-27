---
type: eval
title: 'Eval: ovsq-keyless-local-sync'
description: 'Definition of done for ovsq-keyless-local-sync: 8 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T19:10:05+00:00'
slug: ovsq-keyless-local-sync
signoff:
  signer: delegated:jasperginn@gmail.com/implementer
  hash: dcf51eef591d1ef8b39109fc94615f47f858ed01b32d0633b5aa0ec4a70e9681
  at: '2026-11-27T19:10:05+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: Vault has an identity-token role local-ov-sync with client id seaweedfs, ttl 900 and the literal claim local_ov_sync = JasperHG90/local, readable only through a policy on that one token path carried by a group whose sole member is the operator entity
  Fails when: the role is missing, its client id, ttl or template differ, the policy names any other path, or the group has a member other than vault_identity_entity.operator
- r2: the rendered SeaweedFS IAM config has a role local-ov-sync trusting the vault provider only when oidc:local_ov_sync and oidc:sub (the operator entity id) both match by StringEquals, with a policy allowing only GetObject, PutObject and DeleteObject on arn:aws:s3:::ov-sync/JasperHG90/local/*, and no ci-* role names local_ov_sync
  Fails when: either condition is missing or not StringEquals, the policy allows another action or resource, or a ci-* role trusts local_ov_sync
- r3: the ov-sync consumer maps JasperHG90/local/ to viking://user/jasper/resources/local/, and no mapped folder is viking://user/jasper/resources/ itself or an ancestor of another mapped folder
  Fails when: the entry is missing or points elsewhere, or any mapped folder equals or contains resources/ or another mapped folder
- r4: localstack ov-sync-env mints the local-ov-sync token with the session's Vault token, posts it to SeaweedFS STS with DurationSeconds=900 and RoleArn arn:aws:iam::role/local-ov-sync, and prints exactly three export lines for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN on stdout
  Fails when: the STS request lacks DurationSeconds=900 or names another role, or stdout holds anything but the three export lines
- r5: localstack ov-sync-env prints nothing on stdout and exits non-zero when Vault refuses the token read or STS refuses the swap, with the reason on stderr
  Fails when: stdout is non-empty or the exit code is 0 on a Vault 403 or an STS error
- r6: a how-to for syncing a local folder with ovsq exists and passes the how-to skeleton check, and the knowledge bundle is consistent
  Fails when: the page is missing, fails test_how_to_skeleton, or kmctl check fails
- r7 (judgment): after both roots are applied, eval "$(localstack ov-sync-env)" then an ovsq run with prefix JasperHG90/local and subdir projects/notes lands its files under viking://user/jasper/resources/local/projects/notes/, the credentials expire about 15 minutes after minting, and the same credentials get AccessDenied on a put under ov-sync/JasperHG90/localstack/
  Fails when: the files do not appear, the Expiration is not about 15 minutes out, or the put outside the prefix succeeds
- r8: the repo gates pass
  Fails when: just pre_commit or the cli test suite exits non-zero
