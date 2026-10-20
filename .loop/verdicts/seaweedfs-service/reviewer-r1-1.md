---
type: verdict
title: 'Verdict: seaweedfs-service reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-service: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T05:41:31+00:00'
slug: seaweedfs-service
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

Fail on one blocking finding. The code is right. The jobspec, volume,
secret, firewall rule and scrape match the plan and the spike 3 flag set,
and the live evidence meets r2 to r4. The blocker is the unplanned
`nomad job stop ov-dash`. Only two .okf pages record it, and the
minio-removal plan, which they say restarts ov-dash, never mentions it.
f2 and f3 are small fixes that do not need another review.

## Checked

- Gates: `loopctl gate stamp` from the worktree, run by me: `pass gate
  pre_commit`, `pass gate cli_tests`, `pass eval-row r1`, `stamp green:
  11e5335f92f3b38810f5a6682f8f53a5254e3c61c177e8b1b72b9dedd5574f15`.
- Code read in full: seaweedfs.hcl, test_seaweedfs_jobspec.py, the diffs
  to services.tf, secrets.tf and prometheus.hcl, and the new component page
  and ADR. Image pinned to 4.48, every flag from spike 3 is present, only
  `s3`/`metrics` are in `network` and `config.ports`, and the service tags
  are `["http"]`. The template's `${seaweedfs_secret}` interpolates
  `.path` the same way minio does. `$${attr...}` is escaped for
  templatefile. The secret has `special = false`, so it renders into JSON
  safely. Mounting a rendered `local/` file onto an absolute path has
  precedent in bifrost.hcl and grafana.hcl. The volume sizing copies
  minio_data, as the plan asks.
- r1: the test asserts the image floor (it rejects a floating tag through
  the regex), each flag as a quoted argument, copy_1 = 2, the mapped port
  labels and the s3 tag. It matches fails_when except for the mount gap in
  f2.
- r2 (judgment, met): stdout.txt shows deployment d2334fd0 successful with
  1 healthy. With no update block, Nomad's default `health_check =
  "checks"` applies, so the Consul /healthz check passed. s3check.py ran
  mb/put/list/delete/rb with the admin key from Vault. It used boto3, not
  the aws CLI, which exercises the same S3 calls. Six buckets each took a
  1 KiB write and read it back.
- r3 (judgment, met): a probe from a LAN-side host found only 8333 and 9327
  open. 9333/19333, 8080/18080, 8888/18888 and 18333 were closed. The list
  covers every master, volume, filer and S3 gRPC port.
- r4 (judgment, met): Prometheus through Grafana's proxy shows
  `seaweedfs 192.168.2.29:9327 up=1` and minio up=1. MinIO's alloc
  4cf10997 is still version 13 and 15 days old. The apply touched 5 new
  resources plus the prometheus job. The s3 tag stays with MinIO.
- r5 (judgment, met): the component page covers loopback binds, the S3 gRPC
  port, the readOnly flag, volume growth and the Ed25519/EdDSA trap. The ADR
  rejects Garage and MinIO built from source, with reasons.
- I tried to read the live alloc's master.toml and logs (`nomad alloc fs`,
  `alloc exec`). Both returned 403 for the operator token, so I could not
  confirm the mount live.
- Where the ov-dash stop is recorded: I grepped every later plan in
  .loop/plans for ov-dash and found nothing. components/ov-dash.md is silent
  too.

## Findings

- f1 (missing, blocking): record the ov-dash stop where the work that undoes
  it will see it. In the worktree: components/ov-dash.md, plus the
  orangepi4a jobs-table row marked as stopped. Outside it: the operator
  must add a "start ov-dash and check it places" step to the minio-removal
  plan, and a note for the applications-root tickets that nomad_job.ov_dash
  will show as drift and queue. Another option is to declare the stop in
  Terraform (for example count 0 or a flag on the ov-dash job) so it is not
  invisible state. Pick one and say which. I want to see the fix again
  because a wrong one leaves a user-facing service down for good.
- f2 (test-strength, non-blocking): also assert the
  `local/master.toml:/etc/seaweedfs/master.toml` mount in the test.
- f3 (docs, non-blocking): update the summary line, or ack it.

## Notes

The implementer was right not to bypass the changed SSH host key on
orangepi4a. But the Terraform firewall provisioner does not check host
keys, and it pushed the new ufw rule over that same connection. The
operator should confirm the key before the next apply that touches
orangepi4a. The plan review guessed about 580 MB free on the node. The
real figure was under 128 MB, and the ADR and component page now say so.
