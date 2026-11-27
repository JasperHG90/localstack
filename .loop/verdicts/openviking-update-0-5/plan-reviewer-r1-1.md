---
type: verdict
title: 'Verdict: openviking-update-0-5 plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of openviking-update-0-5: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-27T13:04:52+00:00'
slug: openviking-update-0-5
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk breaks this plan. Risk 1 is settled by the spike, and the
plan's claims about ov-ext 0.8.0, ov-postgres 0.7.0 and OpenViking 0.5.6 hold
against the code.

## Checked

### Risk 1 (first boot on the live table)

Settled by spike:openviking-update-0-5/2. run.json exits 0 and stdout's
REPORT matches the outcome: reconcile 0.62 s, md5 backfill of 50,000 rows in
150.5 s, query p95 48 ms and loop lag max 77 ms during it, all four PASS
lines printed. The 60m healthy_deadline in openviking.hcl leaves a large
margin even if the live table is several times 50k. The limits the spike
names (live row count not measured, local VikingFS rather than SeaweedFS)
add wait, not CPU, and the backfill runs after the bind, so they do not
reach the healthy deadline.

### Claims checked against the code

- ov-ext 0.8.0 (tag ov-ext-v0.8.0 = 10ffca5): REMOVED_SETTINGS holds exactly
  rerank_max_calls and rerank_final, and the validator raises when either is
  in the environment. With those two dropped, every other OV_RETRIEVAL_* the
  jobspec sets loads into HybridSettings (run against the checkout), and the
  OV_REFLECT_* set plus the rendered DELTAS_DSN loads into ReflectSettings.
- The plan's claim that held-back documents rank below every rerank score is
  true: `_rank_below_the_model` in ov_ext/retrieval/retriever.py.
- ov.conf.json custom_params validate against PgVectorParams at v0.7.0
  (extra=forbid), so ALLOWED_CUSTOM_PARAMS needs no change.
- The rendered ov.conf loads under openviking 0.5.6: load_server_config,
  OpenVikingConfig.from_dict and validate_server_config all pass, and the OIDC
  plugin reports its config valid. auth_mode oidc with root_api_key set
  covers the 0.5.1 root-key requirement.
- `--with-bot` behaves as in 0.4.17.1 (exit 1 if VikingBot cannot start),
  so no new failure there. /health still answers 200 without credentials
  (0.4.23 only changed invalid-credential probes), which is what the Nomad
  check sends.
- Clients: ov-sync-consumer still sends `"timeout": 120` to content/write and
  resources; 0.5.6 keeps the field as deprecated, accepted and ignored, so
  the extra=forbid request models do not reject it. Hermes' create_parent
  patch still matches AddResourceRequest. The alert-rule metric names
  (retrieval_requests_total, rerank_fallback_total, zero_result_total,
  vector_scanned_total, *_readiness) are all still emitted in 0.5.6.
- The 2.0 facts match the prose. O1 needs O2 (ov-ext 0.8.0 will not start
  while the two vars are set), O2 is a support change, and O3 is independent.

## Findings

None.

## Notes

For the build, not findings:

- `just verify` will fail as written. Its second step runs
  `python -m ov_retrieval --help`, and neither ov-ext 0.7.1 nor 0.8.0 ships
  an `ov_retrieval` module (only `ov_ext`). The step should be
  `-m ov_ext --help`. O1 names `just verify` as a check, so the justfile
  belongs in O1's touches. The docstring of scripts/check_openviking_config.py
  also still says `python -m ov_retrieval`. Both are one-line fixes and fail
  loudly, so they do not put the plan at risk.
- ov-sync-consumer's 120 s server-side wait bound is gone (0.5.1 ignores
  `timeout`), so a slow write now ends at the client's 150 s HTTP timeout
  instead. This only matters if writes take that long. Worth watching in
  the outcome's ov-sync-consumer check.
