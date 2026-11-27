---
type: eval
title: 'Eval: openviking-update-0-5'
description: 'Definition of done for openviking-update-0-5: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T12:48:50+00:00'
slug: openviking-update-0-5
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: deebe786efff8a1bb85341728a3e5b3b07705ca5f95e18e93f59936f26ee6d16
  at: '2026-11-27T12:48:50+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: services.tf pins openviking_base_image to ghcr.io/volcengine/openviking:v0.5.6 and openviking_image to ghcr.io/jasperhg90/openviking:v0.5.6-1, and Dockerfile.openviking installs ov-postgres at tag ov-postgres-v0.7.0 and ov-ext at tag ov-ext-v0.8.0.
  Fails when: either image line names another tag, or either git pin names another tag or a branch
- r2: scripts/check_openviking_config.py fails when openviking.hcl sets OV_RETRIEVAL_RERANK_MAX_CALLS or OV_RETRIEVAL_RERANK_FINAL, and the committed openviking.hcl sets neither.
  Fails when: the check passes with either variable set, or openviking.hcl still sets one
- r3: The viking_write tool description in the Hermes openviking_tools plugin says mode=create overwrites an existing file, and no longer says the file must not exist.
  Fails when: the description still claims create refuses an existing file, or does not say it overwrites
- r4 (judgment): After the apply, job openviking's deployment is healthy on v0.5.6-1, /health reports v0.5.6, a reranked find and a reranked search return results, and a Hermes viking_search returns memories.
  Fails when: any of those fails, or its evidence is not recorded in the review
