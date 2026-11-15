---
type: eval
title: 'Eval: ci-openviking-sync'
description: 'Definition of done for ci-openviking-sync: 10 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:20:06+00:00'
slug: ci-openviking-sync
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: ec37655a6152c88ef5d0ae97694909f1174b48c9701cb2b17dbed5056b31d3b6
  at: '2026-11-15T20:20:06+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: sync.py uploads only git-tracked files under the folders whose sha256 differs from the manifest, to <owner>/<repo>/<path>
  Fails when: an unchanged file is uploaded, a changed or new file is not, an untracked file is uploaded, or a key lacks the <owner>/<repo>/ prefix
- r2: sync.py deletes the bucket key of every manifest entry whose file is gone, and drops it from the new manifest
  Fails when: a removed file's key is not deleted, or stays in the written manifest, or a present file's key is deleted
- r3: a run with no change uploads nothing, deletes nothing, and treats a missing manifest (NoSuchKey) as empty
  Fails when: a no-change run calls put or delete, or a missing manifest makes the run fail
- r4: when an upload or delete fails, sync.py exits non-zero and writes a manifest holding only what is true in the bucket: the old entries plus the uploads and deletes that succeeded, so a file uploaded in a failed run and deleted before the next run is still removed
  Fails when: the run exits 0, the manifest records a failed upload's new hash or drops a failed delete's entry, or a file uploaded in the failed run and then deleted stays in the bucket after the next successful run
- r5: the sync workflow never runs on pull_request or pull_request_target, sets environment lab, id-token write, a timeout, and a concurrency group that does not cancel in progress
  Fails when: any of those is missing or a pull_request trigger is present
- r6: every SeaweedFS CI policy in the IAM config allows only GetObject, PutObject and DeleteObject on its own arn:aws:s3:::ov-sync/<owner>/<repo>/* and every CI role's trust pins ci_repository with StringEquals
  Fails when: a CI policy names another prefix, a wildcard bucket resource, a list action, or a role trusts without the ci_repository condition
- r7: the Terraform roots stay formatted and valid
  Fails when: fmt or validate fails
- r8 (judgment): after apply, a push to main adding a docs page with a marker finishes the workflow in under 2 minutes, uploads one object to s3://ov-sync/JasperHG90/localstack/docs/..., records its hash in the manifest; a no-change rerun uploads nothing; deleting the page deletes the object and its entry; the job's credential is refused a write under another repo's prefix
  Fails when: any of those is not shown in the run logs and bucket listing, or the run takes 2 minutes or more
- r9 (judgment): no S3, Vault or Tailscale credential is stored in a committed file or a GitHub repository or environment secret
  Fails when: a credential appears in the diff or the sync needs a stored secret
- r10 (judgment): the decision record, component pages, explanation page, the how-to (per the how-to skeleton) and the GitHub Actions reference inputs table describe the action as built
  Fails when: a page is missing or disagrees with the action
