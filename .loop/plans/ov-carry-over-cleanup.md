---
type: plan
title: 'Plan: ov-carry-over-cleanup'
description: Remove the ov-carry-over job, its SeaweedFS user and its Vault key once the operator signs off on the carried-over content.
slug: ov-carry-over-cleanup
epic: ov-reset
depends_on: [ov-carry-over]
status: draft
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T16:54:46+00:00'
---

# ov-carry-over-cleanup

Relayed from: ov-carry-over, whose plan leaves removing its helpers to a
follow-up once the operator has checked the carried content.

## Intent

`ov-carry-over` adds a parameterized Nomad job, a SeaweedFS user that can
read the old `openviking` bucket and write `openviking-v2`, and that user's
key in Vault. Once the operator has checked clips, blogs and leo in the new
instance, nothing needs them, and the key is a standing path into the
backup. Remove the job, the user, its policy and the Vault key, and the
tests and docs that describe them. Outcome: after the apply, the key no
longer authenticates to SeaweedFS, `nomad job status ov-carry-over` finds no
job, and the old bucket's object count is unchanged.

## Could invalidate this plan

none
