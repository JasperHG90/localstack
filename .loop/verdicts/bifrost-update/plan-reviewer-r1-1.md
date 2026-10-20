---
type: verdict
title: 'Verdict: bifrost-update plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of bifrost-update: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T08:55:03+00:00'
slug: bifrost-update
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. Both listed risks are settled by spikes
whose output backs the claim. The plan's statements about the repo hold: the
pin, the provider constraint, the jobspec config keys, the smoke script's auth
probe and the dashboard queries are where and what the plan says.

## Checked

- Risk 1 (provider 0.1.1 against 2.3.1): spike 1 `stdout.txt` shows three keys
  created on v2.3.1, a plan with "No changes", an in-place weight update and a
  second clean plan. Spike 4 covers the path the live apply takes: keys made on
  v2.0.0, the same Postgres store migrated by v2.3.1, ids and `sk-bf-` values
  kept, plan exit 0, three keys returning 200 and a bogus key 401, then a clean
  in-place update. Both exited 0. The spike's resource shape (three alphabetical
  provider_configs with `key_ids = ["*"]`) matches `bifrost_virtual_key.hermes`,
  `.memex` and `.openviking` in `deployments/applications/services.tf`.
- Risk 2 (rerank and embeddings through embark): spike 3 shows a bare-string
  rerank returning 200 on both versions, identical object-form bodies reaching
  the stub, which validates them with embark v0.2.1's own request models, and
  embeddings carrying `routing_info.provider = embark`. Spike 2 is the
  superseded duplicate, as its README says.
- Repo claims: `bifrost_version = "2.0.0"` at services.tf:876 feeds the image
  tag in `services/bifrost.hcl:40`. The provider is `~>0.1.0` in `providers.tf`.
  `bifrost.hcl` sets `auth_config.is_enabled` and `enforce_auth_on_inference`
  explicitly. `scripts/bifrost_smoke.py:112` asserts the `virtual_key_not_found`
  type, which is the line item 3 changes. `EXPECTED_VIRTUAL_KEYS` names four keys
  (Leo, hermes, jasper-laptop-cc, memex), which matches "the four named virtual
  keys". Every dashboard query in `grafana/bifrost.json` aggregates with `sum`
  or `sum by`, so a new `app` label does not split a panel. `openviking.hcl:11`
  holds the ">= 2.0.0" claim the plan leaves alone.

## Findings

None.

## Notes

Gaps the spikes leave, none of which can break the plan: the live store also
holds UI-made keys (Leo, jasper-laptop-cc) that no spike migrated, and the
2.3.0 unique index on `value_hash` runs over them. A failed migration would
stop Bifrost from starting rather than corrupt data, and the `pg_dump` in item 2
covers the rollback. The new name `access_not_found` comes from release notes
and was not seen in a spike. If it is wrong, the smoke run finds out on the
first try.
