---
type: plan
title: 'Plan: seaweedfs-cutover-openviking-reviewer-f2'
description: Deferred hardening from seaweedfs-cutover-openviking, reviewer finding f2 in review round 1.
tags:
- plan
- hardening
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T07:20:08+00:00'
slug: seaweedfs-cutover-openviking-reviewer-f2
status: draft
epic: seaweedfs-migration
depends_on: []
priority: null
---

# seaweedfs-cutover-openviking-reviewer-f2

Relayed from: seaweedfs-cutover-openviking, reviewer finding f2 in review round 1

## Intent

A dispatch with any bucket name that has no prefix under gcs:<bucket>/minio/ exits 0 with 'nothing to restore'. Exit codes are the operator's only signal, so a typo (`bucket=openvking`) or a backup that never ran reads the same as a successful restore. Refuse any name outside the four durable buckets with its own exit code. A durable bucket with no prefix can stay exit 0, as it does for models and datalake. at deployments/infrastructure/services/restore-s3.hcl:54.

## Could invalidate this plan

- none
