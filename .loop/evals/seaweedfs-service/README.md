---
type: eval
title: 'Eval: seaweedfs-service'
description: 'Definition of done for seaweedfs-service: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:54:55+00:00'
slug: seaweedfs-service
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 54fe6b811f95e16a25f6fb810b6bbc5bec812ac44670804a1c56ba4af73be592
  at: '2026-10-19T20:54:55+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The SeaweedFS jobspec pins an exact image tag no older than 4.40, starts weed server with -s3.iam.readOnly=false, loopback binds for master, volume and filer, -s3.ip.bind=0.0.0.0, the volume flags from spike:seaweedfs-service/3 and a master.toml with copy_1 = 2, maps only the S3 and metrics ports, and its Consul service carries no s3 tag.
  Fails when: the image tag is floating or older than 4.40, any of those flags or the master.toml growth setting is missing, a port other than S3 and metrics is mapped, or the seaweedfs service carries the s3 tag
- r2 (judgment): After an apply, the seaweedfs allocation runs with its Consul check passing, and with the admin key aws s3 mb, cp, ls and rb succeed and six buckets made in a row each take a write.
  Fails when: the job is not running, the check is not passing, any of the S3 calls fails, or the evidence is not recorded in the review
- r3 (judgment): From another LAN host, among SeaweedFS's ports on orangepi4a only S3 and metrics answer.
  Fails when: a master, volume, filer or S3 gRPC port answers from the LAN, or the probe output is not recorded
- r4 (judgment): Prometheus shows up{job="seaweedfs"} == 1, and MinIO's job, buckets and routes are unchanged.
  Fails when: the scrape is down or absent, or the apply changed anything MinIO owns
- r5 (judgment): .okf/components/seaweedfs.md describes the job, its flags and traps (loopback binds, S3 gRPC port, readOnly flag, EdDSA keys), and a decision record names SeaweedFS over MinIO with the rejected alternatives.
  Fails when: either page is missing or omits a trap the spikes found
